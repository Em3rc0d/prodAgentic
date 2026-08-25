from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from core.content_identity import build_content_identity
from db.mongo import get_db
from models.content_memory import ContentMemoryKind, ContentMemoryRecord


PREVIEW_MAX_CHARS = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_workspace_id(workspace_id: str) -> str:
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id is required for content memory operations")
    return workspace_id.strip()


def _kind_value(kind: ContentMemoryKind | str) -> str:
    if isinstance(kind, ContentMemoryKind):
        return kind.value
    return ContentMemoryKind(kind).value


def _preview(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("content memory text must be a string")
    return text.strip()[:PREVIEW_MAX_CHARS]


class ContentMemoryRepository:
    """Workspace-scoped deterministic content-memory projection.

    Content memory is an inspectable index/evidence projection. It is never the
    source of truth for publication bytes or text.
    """

    @staticmethod
    def _collection():
        db = get_db()
        return None if db is None else db["content_memory"]

    async def ensure_indexes(self) -> bool:
        collection = self._collection()
        if collection is None:
            return False

        await collection.create_index(
            [("workspace_id", 1), ("run_id", 1), ("kind", 1)],
            unique=True,
            name="uq_content_memory_workspace_run_kind",
        )
        await collection.create_index(
            [("workspace_id", 1), ("normalized_sha256", 1), ("content_status", 1)],
            name="ix_content_memory_exact_lookup",
        )
        return True

    async def upsert(
        self,
        *,
        workspace_id: str,
        run_id: str,
        kind: ContentMemoryKind | str,
        text: str,
        content_status: str,
        external_post_urn: str | None = None,
    ) -> ContentMemoryRecord | None:
        workspace = _require_workspace_id(workspace_id)
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id is required for content memory operations")
        if not isinstance(content_status, str) or not content_status.strip():
            raise ValueError("content_status is required for content memory operations")

        kind_value = _kind_value(kind)
        identity = build_content_identity(text)
        now = _now()
        collection = self._collection()
        if collection is None:
            return None

        query = {
            "workspace_id": workspace,
            "run_id": run_id.strip(),
            "kind": kind_value,
        }
        await collection.update_one(
            query,
            {
                "$setOnInsert": {
                    "memory_id": str(uuid4()),
                    "created_at": now,
                },
                "$set": {
                    "workspace_id": workspace,
                    "run_id": run_id.strip(),
                    "kind": kind_value,
                    "canonicalizer_version": identity.canonicalizer_version,
                    "normalized_sha256": identity.normalized_sha256,
                    "text_preview": _preview(text),
                    "content_status": content_status.strip(),
                    "external_post_urn": external_post_urn,
                    "updated_at": now,
                },
            },
            upsert=True,
        )
        doc = await collection.find_one(query, {"_id": 0})
        return None if doc is None else ContentMemoryRecord.model_validate(doc)

    async def find_exact(
        self,
        *,
        workspace_id: str,
        text: str,
        content_statuses: Iterable[str] | None = None,
    ) -> list[ContentMemoryRecord]:
        workspace = _require_workspace_id(workspace_id)
        identity = build_content_identity(text)
        collection = self._collection()
        if collection is None:
            return []

        query: dict = {
            "workspace_id": workspace,
            "normalized_sha256": identity.normalized_sha256,
        }
        if content_statuses is not None:
            statuses = [status.strip() for status in content_statuses if isinstance(status, str) and status.strip()]
            if not statuses:
                return []
            query["content_status"] = {"$in": statuses}

        cursor = collection.find(query, {"_id": 0}).sort("created_at", 1)
        docs = await cursor.to_list(length=100)
        return [ContentMemoryRecord.model_validate(doc) for doc in docs]
