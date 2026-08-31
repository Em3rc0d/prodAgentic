import os
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import db.content_memory as content_memory_module
from core.content_identity import normalized_sha256
from db.content_memory import ContentMemoryRepository, PREVIEW_MAX_CHARS
from models.content_memory import ContentMemoryKind


def test_workspace_is_mandatory_before_database_access():
    repo = ContentMemoryRepository()

    with pytest.raises(ValueError, match="workspace_id"):
        # Validation occurs before the repository asks for a collection.
        import asyncio
        asyncio.run(repo.find_exact(workspace_id="", text="content"))


@pytest.mark.asyncio
async def test_content_memory_persistence_is_idempotent_and_workspace_scoped(monkeypatch):
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real content-memory gate")

    database_name = f"prodagentic_memory_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    monkeypatch.setattr(content_memory_module, "get_db", lambda: db)
    repo = ContentMemoryRepository()

    try:
        await client.admin.command("ping")
        assert await repo.ensure_indexes() is True

        first_text = "Our first AI agent architecture failed because every task was treated as an agent problem."
        first = await repo.upsert(
            workspace_id="workspace-a",
            run_id="run-001",
            kind=ContentMemoryKind.FINAL_CONTENT,
            text=first_text,
            content_status="READY_FOR_REVIEW",
        )
        assert first is not None
        assert first.workspace_id == "workspace-a"
        assert first.run_id == "run-001"
        assert first.kind == ContentMemoryKind.FINAL_CONTENT
        assert first.canonicalizer_version == "v1"
        assert first.normalized_sha256 == normalized_sha256(first_text)

        repeated = await repo.upsert(
            workspace_id="workspace-a",
            run_id="run-001",
            kind=ContentMemoryKind.FINAL_CONTENT,
            text=first_text,
            content_status="READY_FOR_REVIEW",
        )
        assert repeated is not None
        assert repeated.memory_id == first.memory_id
        assert await db["content_memory"].count_documents({
            "workspace_id": "workspace-a",
            "run_id": "run-001",
            "kind": ContentMemoryKind.FINAL_CONTENT.value,
        }) == 1

        changed_text = "After the failure, deterministic work moved back to ordinary services."
        changed = await repo.upsert(
            workspace_id="workspace-a",
            run_id="run-001",
            kind=ContentMemoryKind.FINAL_CONTENT,
            text=changed_text,
            content_status="READY_FOR_REVIEW",
        )
        assert changed is not None
        assert changed.memory_id == first.memory_id
        assert changed.created_at == first.created_at
        assert changed.normalized_sha256 == normalized_sha256(changed_text)
        assert changed.normalized_sha256 != first.normalized_sha256

        published_a = await repo.upsert(
            workspace_id="workspace-a",
            run_id="run-published-a",
            kind=ContentMemoryKind.PUBLISHED_CONTENT,
            text="Idempotency keys prevented duplicate reservations from webhook retries.",
            content_status="PUBLISHED",
            external_post_urn="urn:li:share:123",
        )
        published_b = await repo.upsert(
            workspace_id="workspace-b",
            run_id="run-published-b",
            kind=ContentMemoryKind.PUBLISHED_CONTENT,
            text="Idempotency keys prevented duplicate reservations from webhook retries.",
            content_status="PUBLISHED",
            external_post_urn="urn:li:share:456",
        )
        assert published_a is not None and published_b is not None

        matches_a = await repo.find_exact(
            workspace_id="workspace-a",
            text="  IDEMPOTENCY keys prevented duplicate reservations   from webhook retries. ",
            content_statuses=["PUBLISHED"],
        )
        assert [record.run_id for record in matches_a] == ["run-published-a"]
        assert matches_a[0].external_post_urn == "urn:li:share:123"

        matches_b = await repo.find_exact(
            workspace_id="workspace-b",
            text="Idempotency keys prevented duplicate reservations from webhook retries.",
            content_statuses=["PUBLISHED"],
        )
        assert [record.run_id for record in matches_b] == ["run-published-b"]

        no_wrong_status = await repo.find_exact(
            workspace_id="workspace-a",
            text="Idempotency keys prevented duplicate reservations from webhook retries.",
            content_statuses=["APPROVED"],
        )
        assert no_wrong_status == []

        long_text = "á" * (PREVIEW_MAX_CHARS + 125)
        bounded = await repo.upsert(
            workspace_id="workspace-a",
            run_id="run-long",
            kind=ContentMemoryKind.FINAL_CONTENT,
            text=long_text,
            content_status="READY_FOR_REVIEW",
        )
        assert bounded is not None
        assert len(bounded.text_preview) == PREVIEW_MAX_CHARS

        indexes = await db["content_memory"].index_information()
        assert indexes["uq_content_memory_workspace_run_kind"]["unique"] is True
        assert "ix_content_memory_exact_lookup" in indexes
    finally:
        await client.drop_database(database_name)
        client.close()
