from __future__ import annotations

from dataclasses import dataclass

from application.quality.integrity import evaluate_owned_asset_bytes
from domain.production.models import ContentRevisionV1, GenerationRunState, GenerationRunV1, RevisionStatus
from domain.quality.models import QAReportV1, QASeverity, QAVerdict
from domain.quality.ports import QualityRepositoryPort
from domain.rendering.ports import AssetStorePort, RenderingRepositoryPort
from domain.production.ports import ProductionRepositoryPort


class QualityAuthorityError(RuntimeError):
    pass


class QualityConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class QualityAuthorityResult:
    report: QAReportV1
    revision: ContentRevisionV1
    run: GenerationRunV1
    reviewable: bool


class QualityAuthorityService:
    """S6 authority boundary: durable QA evidence -> REVIEWABLE, never Approval."""

    def __init__(
        self,
        *,
        production_repository: ProductionRepositoryPort,
        rendering_repository: RenderingRepositoryPort,
        quality_repository: QualityRepositoryPort,
        asset_store: AssetStorePort,
    ):
        self.production_repository = production_repository
        self.rendering_repository = rendering_repository
        self.quality_repository = quality_repository
        self.asset_store = asset_store

    async def apply_report(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        report: QAReportV1,
    ) -> QualityAuthorityResult:
        if report.tenant_id != tenant_id or report.revision_id != revision_id:
            raise QualityAuthorityError("QAReport tenant/revision authority mismatch")

        revision = await self.production_repository.get_revision(tenant_id, revision_id)
        if revision is None:
            raise QualityAuthorityError("ContentRevision not found")
        if revision.status not in {RevisionStatus.QA_PENDING, RevisionStatus.REVIEWABLE}:
            raise QualityAuthorityError("S6 requires QA_PENDING or idempotent REVIEWABLE revision")
        if report.content_spec_digest != revision.content_spec_digest:
            raise QualityAuthorityError("QAReport ContentSpec digest mismatch")
        if not revision.asset_refs:
            raise QualityAuthorityError("S6 requires owned render assets")

        run = await self.production_repository.get_run(tenant_id, revision.run_id)
        if run is None or run.content_id != revision.content_id:
            raise QualityAuthorityError("GenerationRun/ContentRevision authority mismatch")
        if run.state not in {GenerationRunState.QA, GenerationRunState.COMPLETED}:
            raise QualityAuthorityError("GenerationRun is outside the S6 QA boundary")

        assets = []
        render_ids = set()
        render_input_digests = set()
        byte_checks = []
        for asset_id in revision.asset_refs:
            asset = await self.rendering_repository.get_asset(asset_id)
            if asset is None:
                raise QualityAuthorityError("Revision references unavailable AssetV1")
            if asset.tenant_id != tenant_id or asset.revision_id != revision_id:
                raise QualityAuthorityError("AssetV1 tenant/revision lineage mismatch")
            try:
                data = await self.asset_store.get(asset.storage_key)
            except Exception as exc:
                raise QualityAuthorityError("Owned asset bytes are unavailable") from exc
            byte_checks.extend(evaluate_owned_asset_bytes(asset, data))
            assets.append(asset)
            render_ids.add(asset.render_id)
            render_input_digests.add(asset.render_input_digest)

        if any(not check.passed and check.severity == QASeverity.BLOCKING for check in byte_checks):
            raise QualityAuthorityError("Owned asset byte/hash revalidation failed")
        if len(render_ids) != 1 or len(render_input_digests) != 1:
            raise QualityAuthorityError("Revision assets do not share one deterministic render identity")

        render_id = next(iter(render_ids))
        render_result = await self.rendering_repository.get_render_result(render_id)
        if render_result is None:
            raise QualityAuthorityError("RenderResultV1 is unavailable")
        if tuple(asset.asset_id for asset in render_result.assets) != revision.asset_refs:
            raise QualityAuthorityError("RenderResult asset set differs from ContentRevision")
        expected_asset_digests = tuple(asset.sha256 for asset in render_result.assets)
        expected_render_input_digest = next(iter(render_input_digests))
        if report.asset_digests != expected_asset_digests:
            raise QualityAuthorityError("QAReport asset digest set mismatch")
        if report.render_input_digest != expected_render_input_digest:
            raise QualityAuthorityError("QAReport render input digest mismatch")

        await self.quality_repository.save_report(report)

        if report.verdict == QAVerdict.FAIL:
            return QualityAuthorityResult(report=report, revision=revision, run=run, reviewable=False)

        reviewable = await self.quality_repository.mark_revision_reviewable(
            revision_id=revision_id,
            qa_report=report,
            expected_asset_refs=revision.asset_refs,
            expected_content_spec_digest=revision.content_spec_digest,
            expected_visual_spec_digest=revision.visual_spec_digest,
        )
        if reviewable is None:
            raise QualityConflict("ContentRevision changed before REVIEWABLE CAS")

        completed = await self.quality_repository.finish_run_completed(
            run_id=run.run_id,
            revision_id=revision_id,
            qa_report_id=report.qa_report_id,
        )
        if completed is None:
            raise QualityConflict("GenerationRun changed before S6 completion")

        return QualityAuthorityResult(report=report, revision=reviewable, run=completed, reviewable=True)
