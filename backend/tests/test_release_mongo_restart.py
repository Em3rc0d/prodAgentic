import os
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient


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
