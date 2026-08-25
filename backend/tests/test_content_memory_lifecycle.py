import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from core.content_identity import build_content_identity
from core.content_memory import ContentMemoryService
from db.content_memory import ContentMemoryRepository
from models.content_memory import ContentMemoryKind
from models.content_run import ContentRunApprovalRequest, ContentRunEditRequest
import routes.content_runs as content_run_routes


@pytest.mark.asyncio
async def test_real_mongodb_review_detects_only_same_workspace_prior_runs_without_touching_updated_at():
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
        # Same bytes in another workspace must never become a candidate.
        await repository.upsert(
            workspace_id="workspace-b",
            run_id="other-workspace-run",
            kind=ContentMemoryKind.PUBLISHED_CONTENT,
            text="Same engineering insight",
            content_status="PUBLISHED",
            external_post_urn="urn:li:share:other-workspace",
        )
        # Even if the current run already has a published projection, it must
        # not flag itself as its own historical duplicate.
        await repository.upsert(
            workspace_id="workspace-a",
            run_id="review-run",
            kind=ContentMemoryKind.PUBLISHED_CONTENT,
            text="Same engineering insight",
            content_status="PUBLISHED",
            external_post_urn="urn:li:share:self",
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
        assert snapshot["candidates"][0]["external_post_urn"] == "urn:li:share:previous"
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
async def test_real_mongodb_edit_refreshes_memory_and_approval_repairs_stale_hash(monkeypatch):
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real content-memory lifecycle gate")

    database_name = f"prodagentic_memory_review_routes_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        repository = ContentMemoryRepository(db=db)
        await repository.ensure_indexes()
        monkeypatch.setattr(content_run_routes, "get_db", lambda: db)

        original_updated_at = datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc)
        await db["content_runs"].insert_one({
            "run_id": "editable-run",
            "workspace_id": "workspace-a",
            "status": "READY_FOR_REVIEW",
            "final_content": "old review text",
            "visual_prompt": None,
            "visual_render": None,
            "updated_at": original_updated_at,
        })
        await db["posts"].insert_one({"run_id": "editable-run", "final_content": "old review text"})

        initial = await ContentMemoryService(db=db, repository=repository).refresh_review("editable-run")
        initial_memory_id = initial["final_memory_id"]

        edited = await content_run_routes.edit_content_run(
            "editable-run",
            ContentRunEditRequest(final_content="new review text"),
        )
        new_identity = build_content_identity("new review text")

        assert edited["final_content"] == "new review text"
        assert edited["memory_check"]["normalized_sha256"] == new_identity.normalized_sha256
        assert edited["memory_check"]["final_memory_id"] == initial_memory_id

        # Simulate a newer authoritative review revision whose memory snapshot is
        # stale. Approval must refresh the check before freezing approval bytes.
        approval_updated_at = datetime(2026, 8, 25, 12, 45, tzinfo=timezone.utc)
        await db["content_runs"].update_one(
            {"run_id": "editable-run"},
            {"$set": {
                "final_content": "current approval text",
                "updated_at": approval_updated_at,
            }},
        )

        approved = await content_run_routes.approve_content_run(
            "editable-run",
            ContentRunApprovalRequest(include_visual=False),
        )
        approval_identity = build_content_identity("current approval text")

        assert approved["status"] == "APPROVED"
        assert approved["approval"]["final_content"] == "current approval text"
        assert approved["memory_check"]["normalized_sha256"] == approval_identity.normalized_sha256
        assert approved["memory_check"]["normalized_sha256"] != new_identity.normalized_sha256
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
