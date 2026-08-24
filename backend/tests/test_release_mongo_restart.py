import os
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

from db.mongo import _ensure_indexes


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
