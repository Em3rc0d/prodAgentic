import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from db.mongo import _ensure_mk1_production_indexes
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    ContentRevisionV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
)
from domain.tenants.models import TenantContext
from infrastructure.mongo.production import MongoProductionRepository


NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)


def make_run() -> GenerationRunV1:
    return GenerationRunV1(
        run_id="run-s3-1",
        tenant_id="tenant-a",
        content_id="content-1",
        profile_id="profile-1",
        profile_version=1,
        profile_snapshot_digest="a" * 64,
        plan_id="plan-1",
        plan_digest="b" * 64,
        state=GenerationRunState.EDITING,
        contract_versions=("ResearchPackV1@1", "ContentSpecV1@1", "EditorialReviewV1@1"),
        research_pack_ref="research-1",
        content_spec_ref="content-spec-1",
        started_at=NOW,
    )


def make_attempt() -> AgentAttemptEvidenceV1:
    return AgentAttemptEvidenceV1(
        agent_run_id="agent-run-1",
        agent=AgentKind.WRITER,
        contract_version="ContentSpecV1@1",
        prompt_version="s3-writer-v1",
        provider="fixture",
        model="fixture-model",
        attempt=1,
        latency_ms=25,
        input_digest="c" * 64,
        output_digest="d" * 64,
        input_tokens=20,
        output_tokens=40,
        cost_usd=0,
        status=AgentAttemptStatus.SUCCESS,
        created_at=NOW,
    )


def make_revision() -> ContentRevisionV1:
    return ContentRevisionV1(
        revision_id="revision-1",
        tenant_id="tenant-a",
        content_id="content-1",
        run_id="run-s3-1",
        source=RevisionSource.GENERATION,
        content_spec_ref="content-spec-1",
        content_spec_digest="d" * 64,
        status=RevisionStatus.DRAFT,
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_real_mongodb_s3_lineage_survives_repository_restart_and_is_tenant_scoped():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S3 lineage gate")

    database_name = f"prodagentic_s3_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)

        context = TenantContext(tenant_id="tenant-a", actor_id="operator-a")
        repository = MongoProductionRepository(db, context)
        run = make_run()
        attempt = make_attempt()
        revision = make_revision()

        await repository.create_run(run)
        await repository.append_agent_attempt("tenant-a", run.run_id, attempt)
        await repository.save_artifact(
            tenant_id="tenant-a",
            run_id=run.run_id,
            artifact_type="ContentSpecV1",
            artifact_id="content-spec-1",
            digest="d" * 64,
            payload={"schema_version": 1, "content_spec_id": "content-spec-1", "safe": True},
        )
        await repository.save_revision(revision)

        updated = run.model_copy(
            update={
                "state": GenerationRunState.VISUAL_PLANNING,
                "agent_run_refs": (attempt.agent_run_id,),
                "editorial_review_ref": "review-1",
            }
        )
        await repository.update_run(updated)

        # Simulate process/repository restart: no in-memory state is reused.
        reopened = MongoProductionRepository(db, context)
        reloaded_run = await reopened.get_run("tenant-a", run.run_id)
        reloaded_attempts = await reopened.list_agent_attempts("tenant-a", run.run_id)
        reloaded_artifact = await reopened.get_artifact("tenant-a", "content-spec-1")
        reloaded_revision = await reopened.get_revision("tenant-a", revision.revision_id)

        assert reloaded_run is not None
        assert reloaded_run.state == GenerationRunState.VISUAL_PLANNING
        assert reloaded_run.started_at.utcoffset() is not None
        assert reloaded_run.agent_run_refs == (attempt.agent_run_id,)
        assert len(reloaded_attempts) == 1
        assert reloaded_attempts[0] == attempt
        assert reloaded_artifact is not None
        assert reloaded_artifact["digest"] == "d" * 64
        assert reloaded_artifact["payload"]["safe"] is True
        assert reloaded_revision == revision

        assert await db["generation_runs"].count_documents({"tenant_id": "tenant-a"}) == 1
        assert await db["agent_run_attempts"].count_documents({"tenant_id": "tenant-a"}) == 1
        assert await db["production_artifacts"].count_documents({"tenant_id": "tenant-a"}) == 1
        assert await db["content_revisions"].count_documents({"tenant_id": "tenant-a"}) == 1

        other = MongoProductionRepository(
            db,
            TenantContext(tenant_id="tenant-b", actor_id="operator-b"),
        )
        assert await other.get_run("tenant-b", run.run_id) is None
        assert await other.get_artifact("tenant-b", "content-spec-1") is None
        assert await other.get_revision("tenant-b", revision.revision_id) is None
        assert await other.list_agent_attempts("tenant-b", run.run_id) == []

        with pytest.raises(ValueError, match="tenant authority mismatch"):
            await other.get_run("tenant-a", run.run_id)
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_s3_uniqueness_blocks_duplicate_lineage_identity():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S3 uniqueness gate")

    database_name = f"prodagentic_s3_unique_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        repository = MongoProductionRepository(
            db,
            TenantContext(tenant_id="tenant-a", actor_id="operator-a"),
        )
        run = make_run()
        await repository.create_run(run)

        with pytest.raises(Exception):
            await repository.create_run(run)

        attempt = make_attempt()
        await repository.append_agent_attempt("tenant-a", run.run_id, attempt)
        with pytest.raises(Exception):
            await repository.append_agent_attempt("tenant-a", run.run_id, attempt)
    finally:
        await client.drop_database(database_name)
        client.close()
