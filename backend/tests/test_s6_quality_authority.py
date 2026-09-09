from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from application.quality.policy import build_qa_report
from application.quality.service import QualityAuthorityError, QualityAuthorityService
from domain.production.models import (
    ContentRevisionV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
)
from domain.quality.models import QACheckLayer, QACheckV1, QASeverity, RecoveryAction
from domain.rendering.models import AssetV1, RenderResultV1


NOW = datetime(2026, 9, 9, 5, 0, tzinfo=timezone.utc)
DATA = b"owned-s6-png-bytes"


def fixtures():
    run = GenerationRunV1(
        run_id="run-s6-service", tenant_id="tenant-s6", content_id="content-s6",
        profile_id="profile-s6", profile_version=1, profile_snapshot_digest="a" * 64,
        plan_id="plan-s6", plan_digest="b" * 64, state=GenerationRunState.QA,
        contract_versions=("ContentSpecV1@1", "RenderResultV1@1"),
        content_spec_ref="content-spec-s6", visual_spec_ref="visual-spec-s6", started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s6", tenant_id=run.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=run.content_spec_ref, content_spec_digest="c" * 64,
        visual_spec_ref=run.visual_spec_ref, visual_spec_digest="d" * 64,
        asset_refs=("asset-s6",), status=RevisionStatus.QA_PENDING, created_at=NOW,
    )
    asset = AssetV1(
        asset_id="asset-s6", tenant_id=run.tenant_id, revision_id=revision.revision_id,
        render_id="render-s6", visual_spec_id=run.visual_spec_ref, page_id="page-0", page_index=0,
        content_type="image/png", width=1080, height=1350, byte_size=len(DATA),
        storage_key="renders/t-aaaaaaaa/r-bbbbbbbb/x-cccccccc/page-00.png",
        sha256=hashlib.sha256(DATA).hexdigest(), render_input_digest="e" * 64, created_at=NOW,
    )
    render = RenderResultV1(
        render_id=asset.render_id, tenant_id=run.tenant_id, revision_id=revision.revision_id,
        visual_spec_id=run.visual_spec_ref, visual_spec_digest=revision.visual_spec_digest,
        content_spec_digest=revision.content_spec_digest, design_profile_digest="f" * 64,
        render_input_digest=asset.render_input_digest, renderer_name="ChromiumRendererAdapter",
        renderer_version="playwright-1.62.1-chromium-v1", assets=(asset,), started_at=NOW, completed_at=NOW,
    )
    return run, revision, asset, render


def report_for(asset, *, fail=False):
    visual_checks = ()
    if fail:
        visual_checks = (
            QACheckV1(
                code="visual.clipping.p0", layer=QACheckLayer.VISUAL, severity=QASeverity.BLOCKING,
                passed=False, message="clipping", target_ref="page:0",
                recovery_hint=RecoveryAction.LAYOUT_RECOMPOSE,
            ),
        )
    return build_qa_report(
        qa_report_id="qa-s6-service", tenant_id=asset.tenant_id, revision_id=asset.revision_id,
        content_spec_digest="c" * 64, render_input_digest=asset.render_input_digest,
        asset_digests=(asset.sha256,), deterministic_checks=(), semantic_checks=(),
        visual_checks=visual_checks, created_at=NOW,
    )


class ProductionFake:
    def __init__(self, run, revision):
        self.run = run
        self.revision = revision

    async def get_revision(self, tenant_id, revision_id):
        return self.revision if tenant_id == self.revision.tenant_id and revision_id == self.revision.revision_id else None

    async def get_run(self, tenant_id, run_id):
        return self.run if tenant_id == self.run.tenant_id and run_id == self.run.run_id else None


class RenderingFake:
    def __init__(self, asset, render):
        self.asset = asset
        self.render = render

    async def get_asset(self, asset_id):
        return self.asset if asset_id == self.asset.asset_id else None

    async def get_render_result(self, render_id):
        return self.render if render_id == self.render.render_id else None


class AssetStoreFake:
    def __init__(self, data):
        self.data = data

    async def get(self, storage_key):
        return self.data


class QualityFake:
    def __init__(self, run, revision):
        self.run = run
        self.revision = revision
        self.saved = []
        self.mark_calls = 0
        self.finish_calls = 0

    async def save_report(self, report):
        self.saved.append(report)

    async def mark_revision_reviewable(self, *, revision_id, qa_report, expected_asset_refs,
                                       expected_content_spec_digest, expected_visual_spec_digest):
        self.mark_calls += 1
        self.revision = self.revision.model_copy(update={
            "status": RevisionStatus.REVIEWABLE,
            "qa_report_id": qa_report.qa_report_id,
        })
        return self.revision

    async def finish_run_completed(self, *, run_id, revision_id, qa_report_id):
        self.finish_calls += 1
        self.run = self.run.model_copy(update={
            "state": GenerationRunState.COMPLETED,
            "qa_report_refs": (qa_report_id,),
            "completed_at": NOW,
        })
        return self.run


@pytest.mark.asyncio
async def test_s6_quality_authority_pass_persists_exact_report_then_marks_reviewable_and_completed():
    run, revision, asset, render = fixtures()
    quality = QualityFake(run, revision)
    service = QualityAuthorityService(
        production_repository=ProductionFake(run, revision), rendering_repository=RenderingFake(asset, render),
        quality_repository=quality, asset_store=AssetStoreFake(DATA),
    )
    result = await service.apply_report(
        tenant_id=run.tenant_id, revision_id=revision.revision_id, report=report_for(asset)
    )
    assert result.reviewable is True
    assert result.revision.status == RevisionStatus.REVIEWABLE
    assert result.run.state == GenerationRunState.COMPLETED
    assert len(quality.saved) == 1 and quality.mark_calls == 1 and quality.finish_calls == 1


@pytest.mark.asyncio
async def test_s6_quality_authority_fail_report_is_durable_but_never_advances_revision_or_run():
    run, revision, asset, render = fixtures()
    quality = QualityFake(run, revision)
    service = QualityAuthorityService(
        production_repository=ProductionFake(run, revision), rendering_repository=RenderingFake(asset, render),
        quality_repository=quality, asset_store=AssetStoreFake(DATA),
    )
    result = await service.apply_report(
        tenant_id=run.tenant_id, revision_id=revision.revision_id, report=report_for(asset, fail=True)
    )
    assert result.reviewable is False
    assert result.revision.status == RevisionStatus.QA_PENDING
    assert result.run.state == GenerationRunState.QA
    assert len(quality.saved) == 1 and quality.mark_calls == 0 and quality.finish_calls == 0


@pytest.mark.asyncio
async def test_s6_quality_authority_rejects_tampered_owned_bytes_before_persisting_report():
    run, revision, asset, render = fixtures()
    quality = QualityFake(run, revision)
    service = QualityAuthorityService(
        production_repository=ProductionFake(run, revision), rendering_repository=RenderingFake(asset, render),
        quality_repository=quality, asset_store=AssetStoreFake(DATA + b"tamper"),
    )
    with pytest.raises(QualityAuthorityError, match="byte/hash"):
        await service.apply_report(
            tenant_id=run.tenant_id, revision_id=revision.revision_id, report=report_for(asset)
        )
    assert quality.saved == [] and quality.mark_calls == 0 and quality.finish_calls == 0
