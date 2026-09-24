from __future__ import annotations

import hashlib

from application.rendering.copy_resolver import build_renderer_request
from application.rendering.generated_assets import GeneratedAssetResolutionError, GeneratedAssetResolver
from application.rendering.service import (
    RenderAuthorityError,
    RenderConflict,
    RenderExecutionFailed,
    RenderIntegrityError,
    RenderService,
    RenderingResult,
)
from application.visual.validation import VisualSpecValidationError, validate_visual_spec
from domain.production.models import GenerationFailureV1, GenerationRunState, RevisionStatus
from domain.rendering.ports import AssetStorePortError, ImageGenerationPort, RendererPortError
from domain.visual.models import (
    AssetRequirementKind,
    ImageBlockV1,
    RenderStrategy,
    VisualFormat,
    canonical_visual_sha256,
)


_SOURCE_FALLBACK_POLICY_VERSION = "r4-source-fallback-v1"


def _source_optional_fallback_spec(visual_spec):
    """Supersede optional generated imagery with a deterministic composition.

    The current R4 planner only creates GENERATED_IMAGE source requirements as
    decorative enhancement layers. If that provider cannot satisfy the request,
    copy and layout authority can continue without silently weakening integrity
    checks. Existing/tampered owned bytes never enter this path.
    """

    requirements = tuple(visual_spec.asset_requirements)
    if not requirements:
        raise ValueError("source fallback requires at least one generated asset requirement")
    if any(item.kind != AssetRequirementKind.GENERATED_IMAGE for item in requirements):
        raise ValueError("source fallback cannot remove non-generated asset authority")

    requirement_ids = {item.requirement_id for item in requirements}
    removed = 0
    pages = []
    for page in visual_spec.pages:
        blocks = []
        for block in page.blocks:
            if isinstance(block, ImageBlockV1) and block.asset_requirement_ref in requirement_ids:
                removed += 1
                continue
            blocks.append(block)
        pages.append(page.model_copy(update={"blocks": tuple(blocks)}))

    if removed == 0:
        raise ValueError("source fallback found no generated image block to remove")

    original_digest = canonical_visual_sha256(visual_spec)
    identity = hashlib.sha256(
        f"{_SOURCE_FALLBACK_POLICY_VERSION}|{original_digest}".encode("utf-8")
    ).hexdigest()

    strategy = visual_spec.render_strategy
    if visual_spec.format == VisualFormat.SINGLE_IMAGE:
        strategy = RenderStrategy.COMPOSED_STATIC

    return visual_spec.model_copy(
        update={
            "visual_spec_id": f"vs-{identity}",
            "render_strategy": strategy,
            "visual_pattern": "r4.source_fallback.v1",
            "pages": tuple(pages),
            "asset_requirements": (),
            "supersedes_visual_spec_id": visual_spec.visual_spec_id,
        }
    )


class R4RenderService(RenderService):
    """R4 generated-source extension over the certified S5 render lifecycle.

    Generated imagery is resolved to immutable product-owned bytes before the
    RendererRequest exists. The inherited S5 persistence/integrity path remains
    authoritative for final PNG assets, revision binding and restart recovery.
    """

    def __init__(self, *, image_generator: ImageGenerationPort | None = None, **kwargs):
        super().__init__(**kwargs)
        self.image_generator = image_generator

    async def render_revision(self, *, tenant_id: str, revision_id: str) -> RenderingResult:
        revision = await self.production_repository.get_revision(tenant_id, revision_id)
        if revision is None:
            raise RenderAuthorityError("ContentRevision not found")
        if revision.tenant_id != tenant_id:
            raise RenderAuthorityError("ContentRevision tenant authority mismatch")
        if revision.status not in {RevisionStatus.DRAFT, RevisionStatus.QA_PENDING}:
            raise RenderAuthorityError("R4 rendering requires a DRAFT or QA_PENDING ContentRevision")
        if revision.qa_report_id is not None:
            raise RenderAuthorityError("R4 cannot render a revision that already owns QA authority")
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
            raise RenderAuthorityError(f"GenerationRun state {run.state.value} is outside the R4 render boundary")

        content = await self._load_content(tenant_id=tenant_id, revision=revision, run=run)
        visual_spec = await self._load_visual_spec(revision=revision, content=content)
        design_profile = await self._load_design_profile(visual_spec=visual_spec)
        try:
            validate_visual_spec(visual_spec, content=content, design_profile=design_profile)
        except VisualSpecValidationError as exc:
            raise RenderAuthorityError("VisualSpec failed integrity revalidation") from exc

        # Claim durable rendering authority before any generated-source provider
        # call. Real UAT proved that resolving images while still in
        # VISUAL_PLANNING could fail before the S5 claim, leaving a zombie run
        # with no durable failure. Once claimed, transient image failures remain
        # retryable in RENDERING and terminal failures become FAILED.
        if run.state == GenerationRunState.VISUAL_PLANNING:
            claimed = await self.rendering_repository.claim_run_rendering(
                run_id=run.run_id,
                visual_spec_ref=visual_spec.visual_spec_id,
            )
            if claimed is None:
                raise RenderConflict("GenerationRun render claim changed concurrently")
            run = claimed

        resolver = GeneratedAssetResolver(
            repository=self.rendering_repository,
            asset_store=self.asset_store,
            image_generator=self.image_generator,
        )
        try:
            resolved_sources = await resolver.resolve(
                tenant_id=tenant_id,
                revision_id=revision.revision_id,
                visual_spec=visual_spec,
                content=content,
                design_profile=design_profile,
            )
        except GeneratedAssetResolutionError as exc:
            if not exc.fallback_allowed:
                if run.state == GenerationRunState.RENDERING:
                    await self._record_generated_failure(run=run, visual_spec=visual_spec, error=exc)
                raise RenderExecutionFailed("R4 generated visual resolution failed closed") from exc

            try:
                fallback_spec = _source_optional_fallback_spec(visual_spec)
                await self.visual_repository.save_visual_spec(fallback_spec)
                fallback_digest = canonical_visual_sha256(fallback_spec)
                rebound = await self.visual_repository.bind_revision_visual(
                    revision_id=revision.revision_id,
                    expected_visual_spec_ref=visual_spec.visual_spec_id,
                    visual_spec_ref=fallback_spec.visual_spec_id,
                    visual_spec_digest=fallback_digest,
                )
                if rebound is None:
                    raise RenderConflict("Generated-source fallback lost revision authority")

                updated_run = run.model_copy(
                    update={
                        "visual_spec_ref": fallback_spec.visual_spec_id,
                        "failure": None,
                        "completed_at": None,
                    }
                )
                await self.production_repository.update_run(updated_run)

                revision = rebound
                run = updated_run
                visual_spec = fallback_spec
                resolved_sources = {}
                validate_visual_spec(
                    visual_spec,
                    content=content,
                    design_profile=design_profile,
                )
            except Exception as fallback_exc:
                if run.state == GenerationRunState.RENDERING:
                    await self._record_generated_failure(run=run, visual_spec=visual_spec, error=exc)
                raise RenderExecutionFailed(
                    "R4 generated visual fallback could not preserve certified authority"
                ) from fallback_exc

        request = build_renderer_request(
            revision_id=revision.revision_id,
            visual_spec=visual_spec,
            content=content,
            design_profile=design_profile,
            renderer_name=self.renderer.name,
            renderer_version=self.renderer.version,
            resolved_assets=resolved_sources,
        )

        existing_result = await self.rendering_repository.get_render_result(request.render_id)

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
            raise RenderExecutionFailed(f"R4 {safe_stage} execution failed closed") from exc

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

    async def _record_generated_failure(self, *, run, visual_spec, error: GeneratedAssetResolutionError) -> None:
        failure = GenerationFailureV1(
            code="R4_IMAGE_GENERATION_FAILED",
            stage="RENDERING",
            retryable=error.retryable,
            safe_message="R4 could not resolve a complete verified owned source-image set.",
        )
        await self.rendering_repository.mark_run_failed(
            run_id=run.run_id,
            visual_spec_ref=visual_spec.visual_spec_id,
            failure=failure,
        )
