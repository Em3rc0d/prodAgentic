from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from application.rendering import r4_service
from application.rendering.generated_assets import GeneratedAssetResolutionError
from application.rendering.r4_service import R4RenderService
from application.rendering.service import RenderExecutionFailed
from domain.production.models import GenerationRunState, RevisionStatus


class _FailingResolver:
    def __init__(self, **kwargs):
        pass

    async def resolve(self, **kwargs):
        raise GeneratedAssetResolutionError("temporary image provider failure", retryable=True)


class _ProductionRepository:
    def __init__(self, *, revision, run):
        self.revision = revision
        self.run = run

    async def get_revision(self, tenant_id, revision_id):
        return self.revision

    async def get_run(self, tenant_id, run_id):
        return self.run


class _RenderingRepository:
    def __init__(self, *, claimed_run):
        self.claimed_run = claimed_run
        self.events = []
        self.failure = None

    async def claim_run_rendering(self, *, run_id, visual_spec_ref):
        self.events.append("claim")
        return self.claimed_run

    async def mark_run_failed(self, *, run_id, visual_spec_ref, failure):
        self.events.append("failure")
        self.failure = failure
        return self.claimed_run


@pytest.mark.asyncio
async def test_r4_claims_rendering_before_generated_asset_failure_and_persists_recovery(monkeypatch):
    revision = SimpleNamespace(
        revision_id="revision-r4-recovery",
        run_id="run-r4-recovery",
        content_id="content-r4-recovery",
        tenant_id="tenant-r4-recovery",
        status=RevisionStatus.DRAFT,
        qa_report_id=None,
        visual_spec_ref="visual-r4-recovery",
        visual_spec_digest="a" * 64,
        content_spec_ref="content-spec-r4-recovery",
        content_spec_digest="b" * 64,
        asset_refs=(),
    )
    run = SimpleNamespace(
        run_id=revision.run_id,
        tenant_id=revision.tenant_id,
        content_id=revision.content_id,
        visual_spec_ref=revision.visual_spec_ref,
        content_spec_ref=revision.content_spec_ref,
        state=GenerationRunState.VISUAL_PLANNING,
    )
    claimed_run = SimpleNamespace(
        **{
            **run.__dict__,
            "state": GenerationRunState.RENDERING,
        }
    )
    production = _ProductionRepository(revision=revision, run=run)
    rendering = _RenderingRepository(claimed_run=claimed_run)
    service = R4RenderService(
        production_repository=production,
        visual_repository=SimpleNamespace(),
        rendering_repository=rendering,
        renderer=SimpleNamespace(name="test-renderer", version="1"),
        asset_store=SimpleNamespace(),
        image_generator=SimpleNamespace(),
    )
    service._load_content = AsyncMock(return_value=SimpleNamespace())
    visual_spec = SimpleNamespace(visual_spec_id=revision.visual_spec_ref)
    service._load_visual_spec = AsyncMock(return_value=visual_spec)
    service._load_design_profile = AsyncMock(return_value=SimpleNamespace())

    monkeypatch.setattr(r4_service, "validate_visual_spec", lambda *args, **kwargs: None)
    monkeypatch.setattr(r4_service, "GeneratedAssetResolver", _FailingResolver)

    with pytest.raises(RenderExecutionFailed, match="generated visual resolution"):
        await service.render_revision(
            tenant_id=revision.tenant_id,
            revision_id=revision.revision_id,
        )

    assert rendering.events == ["claim", "failure"]
    assert rendering.failure is not None
    assert rendering.failure.code == "R4_IMAGE_GENERATION_FAILED"
    assert rendering.failure.stage == "RENDERING"
    assert rendering.failure.retryable is True
