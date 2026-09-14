from __future__ import annotations

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
            # If S5 has already claimed the run, preserve retryability. A failure
            # before claim leaves VISUAL_PLANNING untouched and safe to retry.
            if run.state == GenerationRunState.RENDERING:
                await self._record_generated_failure(run=run, visual_spec=visual_spec, error=exc)
            raise RenderExecutionFailed("R4 generated visual resolution failed closed") from exc

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
