from __future__ import annotations

import struct
from dataclasses import dataclass

from application.rendering.copy_resolver import UnsupportedRenderInput, build_renderer_request
from application.visual.validation import VisualSpecValidationError, validate_visual_spec
from domain.production.models import (
    ContentRevisionV1,
    ContentSpecV1,
    GenerationFailureV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionStatus,
    canonical_sha256 as production_sha256,
    utc_now,
)
from domain.rendering.models import AssetV1, RenderContentType, RendererRequestV1, RenderResultV1, canonical_render_sha256
from domain.rendering.ports import (
    AssetStorePort,
    AssetStorePortError,
    RendererPort,
    RendererPortError,
    RenderingRepositoryPort,
)
from domain.visual.models import DesignProfileV1, VisualSpecV1, canonical_visual_sha256
from domain.visual.ports import VisualProductionAuthorityPort, VisualRepositoryPort


class RenderAuthorityError(RuntimeError):
    pass


class RenderConflict(RuntimeError):
    pass


class RenderIntegrityError(RuntimeError):
    pass


class RenderExecutionFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderingResult:
    run: GenerationRunV1
    revision: ContentRevisionV1
    content: ContentSpecV1
    visual_spec: VisualSpecV1
    design_profile: DesignProfileV1
    renderer_request: RendererRequestV1
    render_result: RenderResultV1


class RenderService:
    """S5 authority: certified VisualSpec -> owned deterministic render bytes.

    S5 never changes ContentSpec/VisualSpec copy authority and never claims QA
    success. A complete render advances the revision only to QA_PENDING and the
    GenerationRun only to QA, where S6 takes over.
    """

    def __init__(
        self,
        *,
        production_repository: VisualProductionAuthorityPort,
        visual_repository: VisualRepositoryPort,
        rendering_repository: RenderingRepositoryPort,
        renderer: RendererPort,
        asset_store: AssetStorePort,
    ):
        self.production_repository = production_repository
        self.visual_repository = visual_repository
        self.rendering_repository = rendering_repository
        self.renderer = renderer
        self.asset_store = asset_store

    async def render_revision(self, *, tenant_id: str, revision_id: str) -> RenderingResult:
        revision = await self.production_repository.get_revision(tenant_id, revision_id)
        if revision is None:
            raise RenderAuthorityError("ContentRevision not found")
        if revision.tenant_id != tenant_id:
            raise RenderAuthorityError("ContentRevision tenant authority mismatch")
        if revision.status not in {RevisionStatus.DRAFT, RevisionStatus.QA_PENDING}:
            raise RenderAuthorityError("S5 requires a DRAFT or QA_PENDING ContentRevision")
        if revision.qa_report_id is not None:
            raise RenderAuthorityError("S5 cannot render a revision that already owns QA authority")
        if revision.visual_spec_ref is None or revision.visual_spec_digest is None:
            raise RenderAuthorityError("ContentRevision has no certified VisualSpec binding")

        run = await self.production_repository.get_run(tenant_id, revision.run_id)
        if run is None:
            raise RenderAuthorityError("GenerationRun not found")
        if run.tenant_id != tenant_id or run.content_id != revision.content_id:
            raise RenderAuthorityError("GenerationRun/ContentRevision authority mismatch")
        if run.visual_spec_ref != revision.visual_spec_ref:
            raise RenderAuthorityError("GenerationRun/ContentRevision VisualSpec mismatch")
        if run.state not in {
            GenerationRunState.VISUAL_PLANNING,
            GenerationRunState.RENDERING,
            GenerationRunState.QA,
        }:
            raise RenderAuthorityError(f"GenerationRun state {run.state.value} is outside the S5 render boundary")

        content = await self._load_content(tenant_id=tenant_id, revision=revision, run=run)
        visual_spec = await self._load_visual_spec(revision=revision, content=content)
        design_profile = await self._load_design_profile(visual_spec=visual_spec)
        try:
            validate_visual_spec(visual_spec, content=content, design_profile=design_profile)
        except VisualSpecValidationError as exc:
            raise RenderAuthorityError("VisualSpec failed S4 integrity revalidation") from exc

        request = build_renderer_request(
            revision_id=revision.revision_id,
            visual_spec=visual_spec,
            content=content,
            design_profile=design_profile,
            renderer_name=self.renderer.name,
            renderer_version=self.renderer.version,
        )

        existing_result = await self.rendering_repository.get_render_result(request.render_id)

        if run.state == GenerationRunState.VISUAL_PLANNING:
            claimed = await self.rendering_repository.claim_run_rendering(
                run_id=run.run_id,
                visual_spec_ref=visual_spec.visual_spec_id,
            )
            if claimed is None:
                raise RenderConflict("GenerationRun render claim changed concurrently")
            run = claimed

        if existing_result is not None:
            await self._verify_result(
                tenant_id=tenant_id,
                revision=revision,
                visual_spec=visual_spec,
                design_profile=design_profile,
                request=request,
                result=existing_result,
            )
            revision = await self._bind_or_verify_revision(
                tenant_id=tenant_id,
                revision=revision,
                visual_spec=visual_spec,
                result=existing_result,
            )
            run = await self._finish_or_verify_run(run=run, visual_spec=visual_spec)
            return RenderingResult(
                run=run,
                revision=revision,
                content=content,
                visual_spec=visual_spec,
                design_profile=design_profile,
                renderer_request=request,
                render_result=existing_result,
            )

        if revision.status == RevisionStatus.QA_PENDING or revision.asset_refs:
            raise RenderIntegrityError("revision owns asset refs but deterministic RenderResult is unavailable")
        if run.state == GenerationRunState.QA:
            raise RenderIntegrityError("GenerationRun reached QA without a deterministic RenderResult")
        if run.state != GenerationRunState.RENDERING:
            raise RenderConflict("GenerationRun is not claimable for rendering")

        try:
            result = await self._execute_and_persist(
                tenant_id=tenant_id,
                revision=revision,
                visual_spec=visual_spec,
                design_profile=design_profile,
                request=request,
            )
        except (RendererPortError, AssetStorePortError, RenderIntegrityError, ValueError) as exc:
            await self._record_failed_run(run=run, visual_spec=visual_spec, error=exc)
            safe_stage = "renderer" if isinstance(exc, RendererPortError) else "asset/integrity"
            raise RenderExecutionFailed(f"S5 {safe_stage} execution failed closed") from exc

        revision = await self._bind_or_verify_revision(
            tenant_id=tenant_id,
            revision=revision,
            visual_spec=visual_spec,
            result=result,
        )
        run = await self._finish_or_verify_run(run=run, visual_spec=visual_spec)
        return RenderingResult(
            run=run,
            revision=revision,
            content=content,
            visual_spec=visual_spec,
            design_profile=design_profile,
            renderer_request=request,
            render_result=result,
        )

    async def _load_content(
        self,
        *,
        tenant_id: str,
        revision: ContentRevisionV1,
        run: GenerationRunV1,
    ) -> ContentSpecV1:
        if run.content_spec_ref != revision.content_spec_ref:
            raise RenderAuthorityError("GenerationRun/ContentRevision ContentSpec mismatch")
        artifact = await self.production_repository.get_artifact(tenant_id, revision.content_spec_ref)
        if artifact is None or artifact.get("artifact_type") != "ContentSpecV1":
            raise RenderAuthorityError("ContentSpecV1 artifact is unavailable")
        try:
            content = ContentSpecV1.model_validate(artifact.get("payload"))
        except Exception as exc:
            raise RenderAuthorityError("persisted ContentSpecV1 payload is invalid") from exc
        digest = production_sha256(content)
        if content.content_spec_id != revision.content_spec_ref:
            raise RenderAuthorityError("ContentSpec identity mismatch")
        if digest != revision.content_spec_digest or artifact.get("digest") != digest:
            raise RenderAuthorityError("ContentSpec digest authority mismatch")
        return content

    async def _load_visual_spec(self, *, revision: ContentRevisionV1, content: ContentSpecV1) -> VisualSpecV1:
        try:
            visual_spec = await self.visual_repository.get_visual_spec(revision.visual_spec_ref)
        except ValueError as exc:
            raise RenderAuthorityError("persisted VisualSpec integrity check failed") from exc
        if visual_spec is None:
            raise RenderAuthorityError("VisualSpecV1 is unavailable")
        if visual_spec.revision_id != revision.revision_id or visual_spec.content_spec_id != content.content_spec_id:
            raise RenderAuthorityError("VisualSpec lineage mismatch")
        if canonical_visual_sha256(visual_spec) != revision.visual_spec_digest:
            raise RenderAuthorityError("ContentRevision VisualSpec digest mismatch")
        return visual_spec

    async def _load_design_profile(self, *, visual_spec: VisualSpecV1) -> DesignProfileV1:
        try:
            profile = await self.visual_repository.get_design_profile(visual_spec.style.design_profile_ref)
        except ValueError as exc:
            raise RenderAuthorityError("persisted DesignProfile integrity check failed") from exc
        if profile is None or profile.digest != visual_spec.style.design_profile_digest:
            raise RenderAuthorityError("VisualSpec DesignProfile lineage is unavailable")
        return profile

    async def _execute_and_persist(
        self,
        *,
        tenant_id: str,
        revision: ContentRevisionV1,
        visual_spec: VisualSpecV1,
        design_profile: DesignProfileV1,
        request: RendererRequestV1,
    ) -> RenderResultV1:
        started_at = utc_now()
        rendered_pages = await self.renderer.render(request)
        if len(rendered_pages) != len(visual_spec.pages):
            raise RenderIntegrityError("renderer output page count differs from VisualSpec")

        assets: list[AssetV1] = []
        for expected_page, rendered_page in zip(visual_spec.pages, rendered_pages, strict=True):
            self._verify_rendered_page(request=request, expected_page=expected_page, rendered_page=rendered_page)
            stored = await self.asset_store.put(
                rendered_page.data,
                tenant_id=tenant_id,
                revision_id=revision.revision_id,
                render_id=request.render_id,
                page_index=rendered_page.page_index,
                content_type=rendered_page.content_type,
            )
            if not await self.asset_store.verify(stored.storage_key, stored.sha256):
                raise RenderIntegrityError("owned asset read-back hash verification failed")

            asset_id = f"asset-{canonical_render_sha256({'render_id': request.render_id, 'page_id': rendered_page.page_id, 'page_index': rendered_page.page_index})}"
            existing_asset = await self.rendering_repository.get_asset(asset_id)
            if existing_asset is not None:
                if (
                    existing_asset.storage_key != stored.storage_key
                    or existing_asset.sha256 != stored.sha256
                    or existing_asset.byte_size != stored.byte_size
                    or existing_asset.page_id != rendered_page.page_id
                    or existing_asset.width != request.canvas_width
                    or existing_asset.height != request.canvas_height
                    or existing_asset.render_input_digest != request.render_input_digest
                ):
                    raise RenderIntegrityError("existing deterministic AssetV1 disagrees with owned bytes")
                asset = existing_asset
            else:
                asset = AssetV1(
                    asset_id=asset_id,
                    tenant_id=tenant_id,
                    revision_id=revision.revision_id,
                    render_id=request.render_id,
                    visual_spec_id=visual_spec.visual_spec_id,
                    page_id=rendered_page.page_id,
                    page_index=rendered_page.page_index,
                    content_type=RenderContentType.PNG,
                    width=request.canvas_width,
                    height=request.canvas_height,
                    byte_size=stored.byte_size,
                    storage_key=stored.storage_key,
                    sha256=stored.sha256,
                    render_input_digest=request.render_input_digest,
                    created_at=utc_now(),
                )
                await self.rendering_repository.save_asset(asset)
            assets.append(asset)

        completed_at = utc_now()
        result = RenderResultV1(
            render_id=request.render_id,
            tenant_id=tenant_id,
            revision_id=revision.revision_id,
            visual_spec_id=visual_spec.visual_spec_id,
            visual_spec_digest=request.visual_spec_digest,
            content_spec_digest=request.content_spec_digest,
            design_profile_digest=design_profile.digest,
            render_input_digest=request.render_input_digest,
            renderer_name=self.renderer.name,
            renderer_version=self.renderer.version,
            assets=tuple(assets),
            started_at=started_at,
            completed_at=completed_at,
        )
        await self.rendering_repository.save_render_result(result)
        await self._verify_result(
            tenant_id=tenant_id,
            revision=revision,
            visual_spec=visual_spec,
            design_profile=design_profile,
            request=request,
            result=result,
        )
        return result

    def _verify_rendered_page(self, *, request: RendererRequestV1, expected_page, rendered_page) -> None:
        if rendered_page.page_id != expected_page.page_id or rendered_page.page_index != expected_page.page_index:
            raise RenderIntegrityError("renderer page identity differs from VisualSpec")
        if rendered_page.width != request.canvas_width or rendered_page.height != request.canvas_height:
            raise RenderIntegrityError("renderer metadata dimensions differ from VisualSpec canvas")
        if rendered_page.content_type != "image/png":
            raise RenderIntegrityError("S5 certified renderer must return image/png")
        width, height = _png_dimensions(rendered_page.data)
        if (width, height) != (request.canvas_width, request.canvas_height):
            raise RenderIntegrityError("owned PNG dimensions differ from VisualSpec canvas")

    async def _verify_result(
        self,
        *,
        tenant_id: str,
        revision: ContentRevisionV1,
        visual_spec: VisualSpecV1,
        design_profile: DesignProfileV1,
        request: RendererRequestV1,
        result: RenderResultV1,
    ) -> None:
        if result.tenant_id != tenant_id or result.revision_id != revision.revision_id:
            raise RenderIntegrityError("RenderResult tenant/revision authority mismatch")
        if result.render_id != request.render_id or result.render_input_digest != request.render_input_digest:
            raise RenderIntegrityError("RenderResult deterministic identity mismatch")
        if result.visual_spec_id != visual_spec.visual_spec_id or result.visual_spec_digest != request.visual_spec_digest:
            raise RenderIntegrityError("RenderResult VisualSpec authority mismatch")
        if result.content_spec_digest != request.content_spec_digest:
            raise RenderIntegrityError("RenderResult ContentSpec digest mismatch")
        if result.design_profile_digest != design_profile.digest:
            raise RenderIntegrityError("RenderResult DesignProfile digest mismatch")
        if result.renderer_name != self.renderer.name or result.renderer_version != self.renderer.version:
            raise RenderIntegrityError("RenderResult renderer version mismatch")
        if len(result.assets) != len(visual_spec.pages):
            raise RenderIntegrityError("RenderResult asset count differs from VisualSpec page count")

        for expected_page, asset in zip(visual_spec.pages, result.assets, strict=True):
            if asset.page_id != expected_page.page_id or asset.page_index != expected_page.page_index:
                raise RenderIntegrityError("RenderResult asset page lineage mismatch")
            if (asset.width, asset.height) != (visual_spec.canvas.width, visual_spec.canvas.height):
                raise RenderIntegrityError("RenderResult asset dimensions mismatch")
            persisted = await self.rendering_repository.get_asset(asset.asset_id)
            if persisted != asset:
                raise RenderIntegrityError("RenderResult references unavailable or altered AssetV1 metadata")
            if not await self.asset_store.verify(asset.storage_key, asset.sha256):
                raise RenderIntegrityError("RenderResult references missing or hash-mismatched owned bytes")

    async def _bind_or_verify_revision(
        self,
        *,
        tenant_id: str,
        revision: ContentRevisionV1,
        visual_spec: VisualSpecV1,
        result: RenderResultV1,
    ) -> ContentRevisionV1:
        expected_refs = tuple(asset.asset_id for asset in result.assets)
        if revision.status == RevisionStatus.QA_PENDING:
            if revision.asset_refs != expected_refs:
                raise RenderConflict("QA_PENDING revision owns a different immutable asset set")
            return revision
        if revision.asset_refs:
            raise RenderConflict("DRAFT revision unexpectedly owns render assets")
        bound = await self.rendering_repository.bind_revision_assets(
            revision_id=revision.revision_id,
            visual_spec_ref=visual_spec.visual_spec_id,
            visual_spec_digest=canonical_visual_sha256(visual_spec),
            expected_asset_refs=(),
            asset_refs=expected_refs,
        )
        if bound is None:
            latest = await self.production_repository.get_revision(tenant_id, revision.revision_id)
            if latest is None or latest.status != RevisionStatus.QA_PENDING or latest.asset_refs != expected_refs:
                raise RenderConflict("ContentRevision asset pointer changed during render completion")
            return latest
        return bound

    async def _finish_or_verify_run(self, *, run: GenerationRunV1, visual_spec: VisualSpecV1) -> GenerationRunV1:
        if run.state == GenerationRunState.QA:
            return run
        if run.state != GenerationRunState.RENDERING:
            raise RenderConflict("GenerationRun cannot transition to QA from current state")
        finished = await self.rendering_repository.finish_run_qa(
            run_id=run.run_id,
            visual_spec_ref=visual_spec.visual_spec_id,
        )
        if finished is None:
            raise RenderConflict("GenerationRun QA transition changed concurrently")
        return finished

    async def _record_failed_run(self, *, run: GenerationRunV1, visual_spec: VisualSpecV1, error: Exception) -> None:
        if run.state != GenerationRunState.RENDERING:
            return
        if isinstance(error, RendererPortError):
            code = "S5_RENDERER_EXECUTION_FAILED"
            retryable = error.retryable
        elif isinstance(error, AssetStorePortError):
            code = "S5_ASSETSTORE_FAILED"
            retryable = error.retryable
        else:
            code = "S5_RENDER_INTEGRITY_FAILED"
            retryable = False
        failure = GenerationFailureV1(
            code=code,
            stage="RENDERING",
            retryable=retryable,
            safe_message="S5 could not produce a complete verified owned asset set.",
        )
        await self.rendering_repository.mark_run_failed(
            run_id=run.run_id,
            visual_spec_ref=visual_spec.visual_spec_id,
            failure=failure,
        )


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RenderIntegrityError("renderer output is not a valid PNG header")
    width, height = struct.unpack(">II", data[16:24])
    return width, height
