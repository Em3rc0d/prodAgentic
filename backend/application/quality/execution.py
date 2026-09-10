from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from application.quality.policy import (
    build_qa_report,
    evaluate_claim_consistency,
    evaluate_render_integrity,
    evaluate_visual_observations,
    select_recovery,
)
from application.quality.service import QualityAuthorityResult, QualityAuthorityService
from application.rendering.copy_resolver import build_renderer_request
from domain.production.models import (
    ContentSpecV1,
    GenerationRunState,
    ResearchPackV1,
    RevisionStatus,
)
from domain.quality.models import (
    QACheckLayer,
    QACheckV1,
    QASeverity,
    RecoveryAction,
    RecoveryDecisionV1,
)
from domain.quality.ports import QualityRepositoryPort, VisualQualityInspectorPort
from domain.rendering.ports import AssetStorePort, RenderingRepositoryPort
from domain.production.ports import ProductionRepositoryPort
from domain.visual.ports import VisualRepositoryPort


class QualityExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class QualityExecutionResult:
    authority: QualityAuthorityResult
    recovery: RecoveryDecisionV1


class QualityExecutionService:
    """Execute S6 checks from durable S3-S5 authority.

    Text-only content bypasses VisualSpec/Renderer by contract but still receives
    semantic and deterministic QA evidence before it can become REVIEWABLE.
    Visual content is inspected against the exact resolved renderer request.
    """

    def __init__(
        self,
        *,
        production_repository: ProductionRepositoryPort,
        rendering_repository: RenderingRepositoryPort,
        visual_repository: VisualRepositoryPort,
        quality_repository: QualityRepositoryPort,
        asset_store: AssetStorePort,
        visual_inspector: VisualQualityInspectorPort,
        recovery_budget: int = 2,
    ):
        self.production_repository = production_repository
        self.rendering_repository = rendering_repository
        self.visual_repository = visual_repository
        self.quality_repository = quality_repository
        self.asset_store = asset_store
        self.visual_inspector = visual_inspector
        self.recovery_budget = recovery_budget
        self.authority = QualityAuthorityService(
            production_repository=production_repository,
            rendering_repository=rendering_repository,
            quality_repository=quality_repository,
            asset_store=asset_store,
        )

    async def execute(self, *, tenant_id: str, revision_id: str) -> QualityExecutionResult:
        revision = await self.production_repository.get_revision(tenant_id, revision_id)
        if revision is None:
            raise QualityExecutionError("ContentRevision not found")
        run = await self.production_repository.get_run(tenant_id, revision.run_id)
        if run is None or run.content_id != revision.content_id:
            raise QualityExecutionError("GenerationRun/ContentRevision authority mismatch")

        if revision.status == RevisionStatus.REVIEWABLE:
            report = await self.quality_repository.get_latest_report_by_revision(tenant_id, revision_id)
            if report is None or report.qa_report_id != revision.qa_report_id:
                raise QualityExecutionError("REVIEWABLE revision is missing exact QA evidence")
            authority = QualityAuthorityResult(report=report, revision=revision, run=run, reviewable=True)
            return QualityExecutionResult(
                authority=authority,
                recovery=select_recovery(report, attempt=report.recovery_attempt, budget=self.recovery_budget),
            )

        content = await self._load_content(tenant_id=tenant_id, revision=revision)
        research = await self._load_research(tenant_id=tenant_id, run=run)
        semantic_checks = evaluate_claim_consistency(content, research)

        if content.format == "text":
            if revision.visual_spec_ref is not None or revision.visual_spec_digest is not None or revision.asset_refs:
                raise QualityExecutionError("Text-only revision unexpectedly owns visual authority")
            claimed = await self.quality_repository.claim_text_revision_qa(
                revision_id=revision.revision_id,
                run_id=run.run_id,
                expected_content_spec_digest=revision.content_spec_digest,
            )
            if claimed is None:
                raise QualityExecutionError("Text-only revision could not enter the S6 QA boundary")
            revision, run = claimed
            deterministic_checks = (
                QACheckV1(
                    code="format.text.no_visual_required",
                    layer=QACheckLayer.DETERMINISTIC,
                    severity=QASeverity.BLOCKING,
                    passed=(
                        revision.visual_spec_ref is None
                        and revision.visual_spec_digest is None
                        and not revision.asset_refs
                    ),
                    message="Text-only ContentSpec must reach review without fabricated visual or asset authority.",
                    target_ref=revision.revision_id,
                    recovery_hint=RecoveryAction.NONE,
                ),
            )
            report = build_qa_report(
                qa_report_id=f"qa-{uuid4().hex}",
                tenant_id=tenant_id,
                revision_id=revision.revision_id,
                content_spec_digest=revision.content_spec_digest,
                render_input_digest=None,
                asset_digests=(),
                deterministic_checks=deterministic_checks,
                semantic_checks=semantic_checks,
                visual_checks=(),
            )
        else:
            if revision.status != RevisionStatus.QA_PENDING or run.state != GenerationRunState.QA:
                raise QualityExecutionError("Visual revision must be rendered before QA execution")
            if revision.visual_spec_ref is None or revision.visual_spec_digest is None or not revision.asset_refs:
                raise QualityExecutionError("Visual revision is missing render authority")

            visual_spec = await self.visual_repository.get_visual_spec(revision.visual_spec_ref)
            if visual_spec is None:
                raise QualityExecutionError("VisualSpecV1 is unavailable")
            design_profile = await self.visual_repository.get_design_profile(visual_spec.style.design_profile_ref)
            if design_profile is None or design_profile.digest != visual_spec.style.design_profile_digest:
                raise QualityExecutionError("DesignProfile lineage is unavailable")

            first_asset = await self.rendering_repository.get_asset(revision.asset_refs[0])
            if first_asset is None:
                raise QualityExecutionError("Revision references unavailable AssetV1")
            render = await self.rendering_repository.get_render_result(first_asset.render_id)
            if render is None:
                raise QualityExecutionError("RenderResultV1 is unavailable")

            renderer_request = build_renderer_request(
                revision_id=revision.revision_id,
                visual_spec=visual_spec,
                content=content,
                design_profile=design_profile,
                renderer_name=render.renderer_name,
                renderer_version=render.renderer_version,
            )
            if renderer_request.render_id != render.render_id or renderer_request.render_input_digest != render.render_input_digest:
                raise QualityExecutionError("Resolved render request differs from persisted RenderResult authority")

            observations = await self.visual_inspector.inspect(renderer_request)
            if len(observations) != len(visual_spec.pages):
                raise QualityExecutionError("Visual QA observation count differs from VisualSpec page count")

            deterministic_checks = evaluate_render_integrity(render, revision.asset_refs)
            visual_checks = evaluate_visual_observations(observations)
            report = build_qa_report(
                qa_report_id=f"qa-{uuid4().hex}",
                tenant_id=tenant_id,
                revision_id=revision.revision_id,
                content_spec_digest=revision.content_spec_digest,
                render_input_digest=render.render_input_digest,
                asset_digests=tuple(asset.sha256 for asset in render.assets),
                deterministic_checks=deterministic_checks,
                semantic_checks=semantic_checks,
                visual_checks=visual_checks,
            )

        recovery = select_recovery(
            report,
            attempt=report.recovery_attempt,
            budget=self.recovery_budget,
        )
        authority = await self.authority.apply_report(
            tenant_id=tenant_id,
            revision_id=revision.revision_id,
            report=report,
        )
        return QualityExecutionResult(authority=authority, recovery=recovery)

    async def _load_content(self, *, tenant_id: str, revision) -> ContentSpecV1:
        artifact = await self.production_repository.get_artifact(tenant_id, revision.content_spec_ref)
        if artifact is None or artifact.get("artifact_type") != "ContentSpecV1":
            raise QualityExecutionError("ContentSpecV1 artifact is unavailable")
        try:
            content = ContentSpecV1.model_validate(artifact.get("payload"))
        except Exception as exc:
            raise QualityExecutionError("persisted ContentSpecV1 payload is invalid") from exc
        if content.content_spec_id != revision.content_spec_ref:
            raise QualityExecutionError("ContentSpec identity mismatch")
        return content

    async def _load_research(self, *, tenant_id: str, run) -> ResearchPackV1:
        if run.research_pack_ref is None:
            raise QualityExecutionError("ResearchPackV1 authority is unavailable")
        artifact = await self.production_repository.get_artifact(tenant_id, run.research_pack_ref)
        if artifact is None or artifact.get("artifact_type") != "ResearchPackV1":
            raise QualityExecutionError("ResearchPackV1 artifact is unavailable")
        try:
            return ResearchPackV1.model_validate(artifact.get("payload"))
        except Exception as exc:
            raise QualityExecutionError("persisted ResearchPackV1 payload is invalid") from exc
