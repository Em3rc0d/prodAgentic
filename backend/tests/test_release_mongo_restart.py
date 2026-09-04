import os
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

from application.tenancy.bootstrap import migrate_bootstrap_tenant
from application.tenancy.context import bootstrap_tenant_id
from db.mongo import _ensure_indexes, _ensure_mk1_foundation_indexes
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


@pytest.mark.asyncio
async def test_real_mongodb_survives_client_restart():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real restart gate")

    database_name = f"prodagentic_release_{uuid4().hex}"
    first_client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    try:
        await first_client.admin.command("ping")
        await first_client[database_name]["content_runs"].insert_one({
            "run_id": "restart-proof-001",
            "status": "APPROVED",
            "content_profile_snapshot": {"profile_id": "profile-001", "version": 3},
            "approval": {"approval_id": "approval-001", "bundle_sha256": "bundle-restart-proof"},
            "schedule": {"status": "SCHEDULED"},
        })
    finally:
        first_client.close()

    # A new client represents a restarted application process with no in-memory state.
    second_client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    try:
        await second_client.admin.command("ping")
        recovered = await second_client[database_name]["content_runs"].find_one({"run_id": "restart-proof-001"})
        assert recovered["status"] == "APPROVED"
        assert recovered["content_profile_snapshot"]["version"] == 3
        assert recovered["approval"]["bundle_sha256"] == "bundle-restart-proof"
        assert recovered["schedule"]["status"] == "SCHEDULED"
        await second_client.drop_database(database_name)
    finally:
        second_client.close()


@pytest.mark.asyncio
async def test_real_mongodb_rejects_duplicate_publication_fingerprint_across_runs():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real publication dedupe gate")

    database_name = f"prodagentic_dedupe_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_indexes(db)

        shared_key = "same-linkedin-author-and-approved-text"
        await db["content_runs"].insert_one({
            "run_id": "dedupe-run-001",
            "status": "PUBLISHED",
            "publication": {"dedupe_key": shared_key, "status": "PUBLISHED"},
        })

        with pytest.raises(DuplicateKeyError):
            await db["content_runs"].insert_one({
                "run_id": "dedupe-run-002",
                "status": "PUBLISHING",
                "publication": {"dedupe_key": shared_key, "status": "PUBLISHING"},
            })
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_bootstrap_migration_and_tenant_isolation(monkeypatch):
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S0 tenant gate")

    database_name = f"prodagentic_s0_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", database_name)
    try:
        await client.admin.command("ping")
        await _ensure_mk1_foundation_indexes(db)
        await db["content_profiles"].insert_one({"profile_id": "legacy-profile"})
        await db["content_runs"].insert_one({"run_id": "legacy-run"})

        first = await migrate_bootstrap_tenant(db)
        second = await migrate_bootstrap_tenant(db)
        expected_tenant = bootstrap_tenant_id()

        assert first.verified and second.verified
        assert first.modified_by_collection["content_profiles"] == 1
        assert second.modified_by_collection["content_profiles"] == 0
        assert await db["tenants"].count_documents({"tenant_id": expected_tenant}) == 1
        assert await db["content_runs"].count_documents({"tenant_id": expected_tenant}) == 1

        tenant_a = TenantScopedMongoRepository(
            db,
            "mk1_s0_fixture",
            TenantContext(tenant_id="tenant-a", actor_id="operator-a"),
        )
        tenant_b = TenantScopedMongoRepository(
            db,
            "mk1_s0_fixture",
            TenantContext(tenant_id="tenant-b", actor_id="operator-b"),
        )
        await tenant_a.insert_one({"fixture_id": "same-visible-id", "value": "private-a"})
        await tenant_b.insert_one({"fixture_id": "same-visible-id", "value": "private-b"})
        assert (await tenant_a.find_one({"fixture_id": "same-visible-id"}))["value"] == "private-a"
        assert (await tenant_b.find_one({"fixture_id": "same-visible-id"}))["value"] == "private-b"
    finally:
        await client.drop_database(database_name)
        client.close()
