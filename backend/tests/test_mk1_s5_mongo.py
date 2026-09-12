from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from db.mongo import _ensure_mk1_production_indexes, _ensure_mk1_rendering_indexes
from domain.production.models import (
    ContentRevisionV1, GenerationRunState, GenerationRunV1,
    RevisionSource, RevisionStatus,
)
from domain.rendering.models import AssetV1, RenderResultV1, canonical_render_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.rendering import MongoRenderingRepository


# Non-zero microseconds are intentional: immutable S5 digest inputs must survive
# Mongo persistence without BSON datetime truncation changing their hash identity.
NOW = datetime(2026, 9, 8, 20, 20, 0, 123456, tzinfo=timezone.utc)


def make_run_and_revision():
    run = GenerationRunV1(
        run_id="run-s5-mongo", tenant_id="tenant-s5-a", content_id="content-s5-mongo",
        profile_id="profile-s5-mongo", profile_version=1, profile_snapshot_digest="a" * 64,
        plan_id="plan-s5-mongo", plan_digest="b" * 64,
        state=GenerationRunState.VISUAL_PLANNING,
        contract_versions=("ContentSpecV1@1", "ContentRevisionV1@1", "VisualSpecV1@1"),
        content_spec_ref="content-spec-s5-mongo", visual_spec_ref="visual-spec-s5-mongo", started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s5-mongo", tenant_id=run.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=run.content_spec_ref,
        content_spec_digest="c" * 64, visual_spec_ref=run.visual_spec_ref, visual_spec_digest="d" * 64,
        status=RevisionStatus.DRAFT, created_at=NOW,
    )
    return run, revision


def make_asset(*, asset_id="asset-s5-mongo", page_index=0):
    return AssetV1(
        asset_id=asset_id, tenant_id="tenant-s5-a", revision_id="revision-s5-mongo",
        render_id="render-s5-mongo", visual_spec_id="visual-spec-s5-mongo",
        page_id=f"page-{page_index}", page_index=page_index, content_type="image/png",
        width=1080, height=1350, byte_size=12345,
        storage_key=f"renders/t-aaaaaaaaaaaaaaaa/r-bbbbbbbbbbbbbbbbbbbbbbbb/x-cccccccccccccccccccccccc/page-{page_index:02d}.png",
        sha256=("e" if page_index == 0 else "f") * 64,
        render_input_digest="9" * 64, created_at=NOW,
    )


@pytest.mark.asyncio
async def test_real_mongodb_s5_render_lineage_survives_restart_and_is_tenant_scoped():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S5 rendering gate")

    database_name = f"prodagentic_s5_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_rendering_indexes(db)

        context = TenantContext(tenant_id="tenant-s5-a", actor_id="operator-s5-a")
        production = MongoProductionRepository(db, context)
        rendering = MongoRenderingRepository(db, context)
        run, revision = make_run_and_revision()
        await production.create_run(run)
        await production.save_revision(revision)

        claimed = await rendering.claim_run_rendering(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert claimed is not None and claimed.state == GenerationRunState.RENDERING
        assert {"RendererRequestV1@1", "AssetV1@1", "RenderResultV1@1"}.issubset(set(claimed.contract_versions))

        asset = make_asset()
        await rendering.save_asset(asset)
        result = RenderResultV1(
            render_id=asset.render_id, tenant_id=context.tenant_id, revision_id=revision.revision_id,
            visual_spec_id=run.visual_spec_ref, visual_spec_digest=revision.visual_spec_digest,
            content_spec_digest=revision.content_spec_digest, design_profile_digest="8" * 64,
            render_input_digest=asset.render_input_digest, renderer_name="ChromiumRendererAdapter",
            renderer_version="playwright-1.62.1-chromium-v1", assets=(asset,),
            started_at=NOW, completed_at=NOW,
        )
        await rendering.save_render_result(result)

        raw_asset = await db["assets"].find_one({"tenant_id": context.tenant_id, "asset_id": asset.asset_id})
        raw_result = await db["render_results"].find_one({"tenant_id": context.tenant_id, "render_id": result.render_id})
        assert raw_asset["created_at"] == asset.model_dump(mode="json")["created_at"]
        assert raw_result["started_at"] == result.model_dump(mode="json")["started_at"]
        assert raw_result["completed_at"] == result.model_dump(mode="json")["completed_at"]

        bound = await rendering.bind_revision_assets(
            revision_id=revision.revision_id, visual_spec_ref=run.visual_spec_ref,
            visual_spec_digest=revision.visual_spec_digest, expected_asset_refs=(), asset_refs=(asset.asset_id,),
        )
        assert bound is not None and bound.status == RevisionStatus.QA_PENDING
        assert bound.asset_refs == (asset.asset_id,) and bound.qa_report_id is None
        finished = await rendering.finish_run_qa(run_id=run.run_id, visual_spec_ref=run.visual_spec_ref)
        assert finished is not None and finished.state == GenerationRunState.QA

        # Reopen all adapters: no process-local lineage is reused.
        reopened_production = MongoProductionRepository(db, context)
        reopened_rendering = MongoRenderingRepository(db, context)
        reloaded_run = await reopened_production.get_run(context.tenant_id, run.run_id)
        reloaded_revision = await reopened_production.get_revision(context.tenant_id, revision.revision_id)
        reloaded_asset = await reopened_rendering.get_asset(asset.asset_id)
        reloaded_result = await reopened_rendering.get_render_result(result.render_id)
        assert reloaded_run is not None and reloaded_run.state == GenerationRunState.QA
        assert reloaded_revision is not None and reloaded_revision.status == RevisionStatus.QA_PENDING
        assert reloaded_revision.asset_refs == (asset.asset_id,)
        assert reloaded_asset == asset
        assert reloaded_result == result
        assert reloaded_asset.created_at.utcoffset() is not None

        # Idempotent replay of deterministic metadata/result is allowed.
        await reopened_rendering.save_asset(asset)
        await reopened_rendering.save_render_result(result)
        assert await db["assets"].count_documents({"tenant_id": context.tenant_id}) == 1
        assert await db["render_results"].count_documents({"tenant_id": context.tenant_id}) == 1

        # Cross-tenant lookups cannot see S5 authority.
        other = MongoRenderingRepository(db, TenantContext(tenant_id="tenant-s5-b", actor_id="operator-s5-b"))
        assert await other.get_asset(asset.asset_id) is None
        assert await other.get_render_result(result.render_id) is None
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_s5_cas_rejects_stale_asset_binding_and_identity_tamper():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S5 CAS gate")

    database_name = f"prodagentic_s5_cas_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_rendering_indexes(db)
        context = TenantContext(tenant_id="tenant-s5-a", actor_id="operator-s5-a")
        production = MongoProductionRepository(db, context)
        rendering = MongoRenderingRepository(db, context)
        run, revision = make_run_and_revision()
        await production.create_run(run)
        await production.save_revision(revision)

        first = await rendering.bind_revision_assets(
            revision_id=revision.revision_id, visual_spec_ref=revision.visual_spec_ref,
            visual_spec_digest=revision.visual_spec_digest, expected_asset_refs=(), asset_refs=("asset-first",),
        )
        assert first is not None and first.asset_refs == ("asset-first",)

        stale = await rendering.bind_revision_assets(
            revision_id=revision.revision_id, visual_spec_ref=revision.visual_spec_ref,
            visual_spec_digest=revision.visual_spec_digest, expected_asset_refs=(), asset_refs=("asset-stale",),
        )
        assert stale is None
        persisted = await production.get_revision(context.tenant_id, revision.revision_id)
        assert persisted is not None and persisted.asset_refs == ("asset-first",)

        asset = make_asset()
        await rendering.save_asset(asset)
        await db["assets"].update_one(
            {"tenant_id": context.tenant_id, "asset_id": asset.asset_id},
            {"$set": {"sha256": "0" * 64}},
        )
        with pytest.raises(ValueError, match="digest mismatch"):
            await rendering.get_asset(asset.asset_id)
    finally:
        await client.drop_database(database_name)
        client.close()
