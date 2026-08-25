import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from core.content_memory import ContentMemoryService
from db.content_memory import ContentMemoryRepository
from models.content_memory import ContentMemoryKind


@pytest.mark.asyncio
async def test_real_mongodb_review_detects_exact_published_duplicate_without_touching_updated_at():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real content-memory lifecycle gate")

    database_name = f"prodagentic_memory_lifecycle_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        repository = ContentMemoryRepository(db=db)
        await repository.ensure_indexes()

        await repository.upsert(
            workspace_id="workspace-a",
            run_id="published-run",
            kind=ContentMemoryKind.PUBLISHED_CONTENT,
            text="Same engineering insight",
            content_status="PUBLISHED",
            external_post_urn="urn:li:share:previous",
        )

        original_updated_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        await db["content_runs"].insert_one({
            "run_id": "review-run",
            "workspace_id": "workspace-a",
            "status": "READY_FOR_REVIEW",
            "final_content": "  same   engineering INSIGHT  ",
            "updated_at": original_updated_at,
        })

        snapshot = await ContentMemoryService(db=db, repository=repository).refresh_review("review-run")
        persisted = await db["content_runs"].find_one({"run_id": "review-run"})

        assert snapshot["status"] == "READY"
        assert snapshot["outcome"] == "EXACT_DUPLICATE"
        assert len(snapshot["candidates"]) == 1
        assert snapshot["candidates"][0]["run_id"] == "published-run"
        assert persisted["updated_at"] == original_updated_at
        assert persisted["memory_check"]["normalized_sha256"] == snapshot["normalized_sha256"]

        final_memories = await repository.find_exact(
            workspace_id="workspace-a",
            text="same engineering insight",
            content_statuses=["READY_FOR_REVIEW"],
            kinds=[ContentMemoryKind.FINAL_CONTENT],
        )
        assert len(final_memories) == 1
        assert final_memories[0].run_id == "review-run"
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_published_projection_uses_immutable_approval_bytes():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real content-memory lifecycle gate")

    database_name = f"prodagentic_memory_publish_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        repository = ContentMemoryRepository(db=db)
        await repository.ensure_indexes()

        await db["content_runs"].insert_one({
            "run_id": "published-run",
            "workspace_id": "workspace-a",
            "status": "PUBLISHED",
            "final_content": "mutable field that must not become publication truth",
            "memory_check": None,
        })
        approval = {
            "approval_id": "approval-immutable",
            "bundle_sha256": "bundle-immutable",
            "final_content": "immutable approved publication bytes",
        }

        result = await ContentMemoryService(db=db, repository=repository).index_published(
            "published-run",
            approval,
            "urn:li:share:immutable",
        )
        persisted = await db["content_runs"].find_one({"run_id": "published-run"})

        assert result["status"] == "READY"
        assert persisted["memory_check"]["published_index_status"] == "READY"

        immutable_matches = await repository.find_exact(
            workspace_id="workspace-a",
            text="immutable approved publication bytes",
            content_statuses=["PUBLISHED"],
            kinds=[ContentMemoryKind.PUBLISHED_CONTENT],
        )
        mutable_matches = await repository.find_exact(
            workspace_id="workspace-a",
            text="mutable field that must not become publication truth",
            content_statuses=["PUBLISHED"],
            kinds=[ContentMemoryKind.PUBLISHED_CONTENT],
        )

        assert len(immutable_matches) == 1
        assert immutable_matches[0].external_post_urn == "urn:li:share:immutable"
        assert mutable_matches == []
    finally:
        await client.drop_database(database_name)
        client.close()
