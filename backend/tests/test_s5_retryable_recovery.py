from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from db.mongo import _ensure_mk1_production_indexes, _ensure_mk1_rendering_indexes
from domain.production.models import GenerationFailureV1, GenerationRunState, GenerationRunV1
from domain.tenants.models import TenantContext
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.rendering import MongoRenderingRepository


NOW = datetime(2026, 9, 8, 20, 30, tzinfo=timezone.utc)


def make_run(run_id: str) -> GenerationRunV1:
    return GenerationRunV1(
        run_id=run_id,
        tenant_id="tenant-s5-recovery",
        content_id=f"content-{run_id}",
        profile_id="profile-s5-recovery",
        profile_version=1,
        profile_snapshot_digest="a" * 64,
        plan_id=f"plan-{run_id}",
        plan_digest="b" * 64,
        state=GenerationRunState.VISUAL_PLANNING,
        contract_versions=("ContentSpecV1@1", "VisualSpecV1@1"),
        content_spec_ref=f"content-spec-{run_id}",
        visual_spec_ref=f"visual-spec-{run_id}",
        started_at=NOW,
    )


@pytest.mark.asyncio
async def test_retryable_s5_failure_stays_recoverable_and_success_clears_failure():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for S5 retryable recovery gate")

    database_name = f"prodagentic_s5_recovery_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_rendering_indexes(db)

        context = TenantContext(tenant_id="tenant-s5-recovery", actor_id="operator-s5")
        production = MongoProductionRepository(db, context)
        rendering = MongoRenderingRepository(db, context)

        run = make_run("run-retryable")
        await production.create_run(run)
        claimed = await rendering.claim_run_rendering(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert claimed is not None and claimed.state == GenerationRunState.RENDERING

        retryable_failure = GenerationFailureV1(
            code="S5_RENDERER_EXECUTION_FAILED",
            stage="RENDERING",
            retryable=True,
            safe_message="Renderer temporarily unavailable.",
        )
        recorded = await rendering.mark_run_failed(
            run_id=run.run_id,
            visual_spec_ref=run.visual_spec_ref,
            failure=retryable_failure,
        )
        assert recorded is not None
        assert recorded.state == GenerationRunState.RENDERING
        assert recorded.failure == retryable_failure
        assert recorded.completed_at is None

        reclaimed = await rendering.claim_run_rendering(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert reclaimed is not None and reclaimed.state == GenerationRunState.RENDERING
        finished = await rendering.finish_run_qa(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert finished is not None and finished.state == GenerationRunState.QA
        assert finished.failure is None
        assert finished.completed_at is None


@pytest.mark.asyncio
async def test_nonretryable_s5_integrity_failure_is_terminal():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for S5 retryable recovery gate")

    database_name = f"prodagentic_s5_terminal_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_rendering_indexes(db)

        context = TenantContext(tenant_id="tenant-s5-recovery", actor_id="operator-s5")
        production = MongoProductionRepository(db, context)
        rendering = MongoRenderingRepository(db, context)

        run = make_run("run-terminal")
        await production.create_run(run)
        claimed = await rendering.claim_run_rendering(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert claimed is not None and claimed.state == GenerationRunState.RENDERING

        terminal_failure = GenerationFailureV1(
            code="S5_RENDER_INTEGRITY_FAILED",
            stage="RENDERING",
            retryable=False,
            safe_message="Owned render bytes failed integrity verification.",
        )
        recorded = await rendering.mark_run_failed(
            run_id=run.run_id,
            visual_spec_ref=run.visual_spec_ref,
            failure=terminal_failure,
        )
        assert recorded is not None
        assert recorded.state == GenerationRunState.FAILED
        assert recorded.failure == terminal_failure
        assert recorded.completed_at is not None
    finally:
        await client.drop_database(database_name)
        client.close()
