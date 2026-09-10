from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.quality.execution import QualityExecutionService
from application.quality.service import QualityAuthorityService
from domain.production.models import (
    ContentRevisionV1,
    ContentSpecV1,
    GenerationRunState,
    GenerationRunV1,
    ResearchPackV1,
    RevisionSource,
    RevisionStatus,
    TextFormatSpecV1,
    canonical_sha256,
)
from domain.quality.models import QAVerdict


NOW = datetime(2026, 9, 10, 20, 30, tzinfo=timezone.utc)


def text_fixtures():
    content = ContentSpecV1(
        content_spec_id="content-spec-r2-text", plan_id="plan-r2-text", language="en",
        title="Text-only authority", hook="A text post should not fabricate visual evidence.",
        body="Keep the S4/S5 bypass explicit and still run semantic QA.", format="text",
        format_spec=TextFormatSpecV1(), claims_used=(),
    )
    research = ResearchPackV1(research_id="research-r2-text", plan_id=content.plan_id, verdict="GO")
    run = GenerationRunV1(
        run_id="run-r2-text", tenant_id="tenant-r2", content_id="content-r2-text", profile_id="profile-r2",
        profile_version=1, profile_snapshot_digest="a" * 64, plan_id=content.plan_id, plan_digest="b" * 64,
        state=GenerationRunState.VISUAL_PLANNING, contract_versions=("ContentSpecV1@1",),
        research_pack_ref=research.research_id, content_spec_ref=content.content_spec_id, started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-r2-text", tenant_id=run.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=content.content_spec_id,
        content_spec_digest=canonical_sha256(content), status=RevisionStatus.DRAFT, created_at=NOW,
    )
    artifacts = {
        content.content_spec_id: {"artifact_type":"ContentSpecV1","payload":content.model_dump(mode="json")},
        research.research_id: {"artifact_type":"ResearchPackV1","payload":research.model_dump(mode="json")},
    }
    return run, revision, artifacts


class ProductionFake:
    def __init__(self, run, revision, artifacts): self.run=run; self.revision=revision; self.artifacts=artifacts
    async def get_revision(self, tenant_id, revision_id): return self.revision if tenant_id==self.revision.tenant_id and revision_id==self.revision.revision_id else None
    async def get_run(self, tenant_id, run_id): return self.run if tenant_id==self.run.tenant_id and run_id==self.run.run_id else None
    async def get_artifact(self, tenant_id, artifact_id): return self.artifacts.get(artifact_id) if tenant_id==self.run.tenant_id else None

class RenderingFake:
    async def get_asset(self, asset_id): return None
    async def get_render_result(self, render_id): return None

class VisualFake:
    async def get_visual_spec(self, visual_spec_id): return None
    async def get_design_profile(self, design_profile_id): return None

class AssetStoreFake:
    async def get(self, storage_key): raise AssertionError("text-only QA must not read AssetStore bytes")

class InspectorFake:
    async def inspect(self, request): raise AssertionError("text-only QA must not invoke visual inspection")

class QualityFake:
    def __init__(self, production): self.production=production; self.reports=[]
    async def get_latest_report_by_revision(self, tenant_id, revision_id): return self.reports[-1] if self.reports else None
    async def claim_text_revision_qa(self, *, revision_id, run_id, expected_content_spec_digest):
        assert expected_content_spec_digest==self.production.revision.content_spec_digest
        self.production.revision=self.production.revision.model_copy(update={"status":RevisionStatus.QA_PENDING})
        self.production.run=self.production.run.model_copy(update={"state":GenerationRunState.QA})
        return self.production.revision,self.production.run
    async def save_report(self, report): self.reports.append(report)
    async def mark_revision_reviewable(self, *, revision_id, qa_report, expected_asset_refs, expected_content_spec_digest, expected_visual_spec_digest):
        assert expected_asset_refs==(); assert expected_visual_spec_digest is None
        self.production.revision=self.production.revision.model_copy(update={"status":RevisionStatus.REVIEWABLE,"qa_report_id":qa_report.qa_report_id})
        return self.production.revision
    async def finish_run_completed(self, *, run_id, revision_id, qa_report_id):
        self.production.run=self.production.run.model_copy(update={"state":GenerationRunState.COMPLETED,"qa_report_refs":(qa_report_id,),"completed_at":NOW})
        return self.production.run


@pytest.mark.asyncio
async def test_r2_text_only_quality_path_reaches_reviewable_without_visual_authority():
    run,revision,artifacts=text_fixtures(); production=ProductionFake(run,revision,artifacts); quality=QualityFake(production)
    service=QualityExecutionService(production_repository=production,rendering_repository=RenderingFake(),visual_repository=VisualFake(),quality_repository=quality,asset_store=AssetStoreFake(),visual_inspector=InspectorFake())
    result=await service.execute(tenant_id=run.tenant_id,revision_id=revision.revision_id)
    assert result.authority.reviewable is True
    assert result.authority.revision.status==RevisionStatus.REVIEWABLE
    assert result.authority.run.state==GenerationRunState.COMPLETED
    assert result.authority.report.verdict==QAVerdict.PASS
    assert result.authority.report.render_input_digest is None
    assert result.authority.report.asset_digests==()
    assert result.authority.report.visual_checks==()
    assert any(check.code=="format.text.no_visual_required" for check in result.authority.report.deterministic_checks)


@pytest.mark.asyncio
async def test_r2_quality_authority_accepts_explicit_text_only_report_boundary():
    run,revision,artifacts=text_fixtures(); production=ProductionFake(run,revision.model_copy(update={"status":RevisionStatus.QA_PENDING}),artifacts); production.run=run.model_copy(update={"state":GenerationRunState.QA}); quality=QualityFake(production)
    from application.quality.policy import build_qa_report
    report=build_qa_report(qa_report_id="qa-r2-text-explicit",tenant_id=run.tenant_id,revision_id=revision.revision_id,content_spec_digest=revision.content_spec_digest,render_input_digest=None,asset_digests=(),deterministic_checks=(),semantic_checks=(),visual_checks=(),created_at=NOW)
    authority=QualityAuthorityService(production_repository=production,rendering_repository=RenderingFake(),quality_repository=quality,asset_store=AssetStoreFake())
    result=await authority.apply_report(tenant_id=run.tenant_id,revision_id=revision.revision_id,report=report)
    assert result.reviewable is True
    assert result.revision.visual_spec_ref is None
    assert result.revision.asset_refs==()
