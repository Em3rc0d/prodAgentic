from datetime import datetime, timezone

from core.content_identity import build_content_identity
from db.content_memory import ContentMemoryRepository
from db.mongo import get_db
from models.content_memory import ContentMemoryKind


LEGACY_WORKSPACE_ID = "legacy-default"
_MEMORY_CANDIDATE_LIMIT = 3


def _now():
    return datetime.now(timezone.utc)


def _published_base_snapshot(identity, indexed_at, *, status: str, error_message: str | None = None) -> dict:
    """Create a complete memory_check when a run has no existing object.

    MongoDB cannot create a dotted child field below an explicit null parent, so
    legacy/current documents with `memory_check: null` must receive the whole
    object atomically before later dotted updates are safe.
    """
    return {
        "status": status,
        "outcome": "CLEAR" if status == "READY" else "DEGRADED",
        "checked_at": indexed_at,
        "canonicalizer_version": identity.canonicalizer_version,
        "normalized_sha256": identity.normalized_sha256,
        "final_memory_id": None,
        "candidates": [],
        "error_message": error_message,
        "published_memory_id": None,
        "published_index_status": status,
        "published_indexed_at": indexed_at,
    }


class ContentMemoryService:
    """Advisory lifecycle integration for deterministic content memory.

    This service never approves, publishes, edits or generates content. It only
    maintains an inspectable projection around authoritative ContentRun data.
    """

    def __init__(self, db=None, repository=None):
        self.db = db if db is not None else get_db()
        self.repository = repository or ContentMemoryRepository(db=self.db)

    async def refresh_review(self, run_id: str) -> dict | None:
        if self.db is None:
            return None

        collection = self.db["content_runs"]
        existing = await collection.find_one({"run_id": run_id})
        if existing is None:
            return None

        final_content = existing.get("final_content")
        if not isinstance(final_content, str) or not final_content.strip():
            return None

        workspace_id = existing.get("workspace_id") or LEGACY_WORKSPACE_ID
        identity = build_content_identity(final_content)
        checked_at = _now()

        try:
            final_memory = await self.repository.upsert(
                workspace_id=workspace_id,
                run_id=run_id,
                kind=ContentMemoryKind.FINAL_CONTENT,
                text=final_content,
                content_status=existing.get("status") or "READY_FOR_REVIEW",
            )
            if final_memory is None:
                raise RuntimeError("Content memory persistence is unavailable")

            exact_matches = await self.repository.find_exact(
                workspace_id=workspace_id,
                text=final_content,
                content_statuses=["PUBLISHED"],
                kinds=[ContentMemoryKind.PUBLISHED_CONTENT],
            )
            candidates = [
                {
                    "memory_id": candidate.memory_id,
                    "run_id": candidate.run_id,
                    "content_status": candidate.content_status,
                    "external_post_urn": candidate.external_post_urn,
                    "text_preview": candidate.text_preview,
                }
                for candidate in exact_matches
                if candidate.run_id != run_id
            ][:_MEMORY_CANDIDATE_LIMIT]

            existing_check = existing.get("memory_check") if isinstance(existing.get("memory_check"), dict) else {}
            snapshot = {
                "status": "READY",
                "outcome": "EXACT_DUPLICATE" if candidates else "CLEAR",
                "checked_at": checked_at,
                "canonicalizer_version": identity.canonicalizer_version,
                "normalized_sha256": identity.normalized_sha256,
                "final_memory_id": final_memory.memory_id,
                "candidates": candidates,
                "error_message": None,
                "published_memory_id": existing_check.get("published_memory_id"),
                "published_index_status": existing_check.get("published_index_status"),
                "published_indexed_at": existing_check.get("published_indexed_at"),
            }
        except Exception as exc:
            existing_check = existing.get("memory_check") if isinstance(existing.get("memory_check"), dict) else {}
            snapshot = {
                "status": "DEGRADED",
                "outcome": "DEGRADED",
                "checked_at": checked_at,
                "canonicalizer_version": identity.canonicalizer_version,
                "normalized_sha256": identity.normalized_sha256,
                "final_memory_id": None,
                "candidates": [],
                "error_message": str(exc),
                "published_memory_id": existing_check.get("published_memory_id"),
                "published_index_status": existing_check.get("published_index_status"),
                "published_indexed_at": existing_check.get("published_indexed_at"),
            }

        # Deliberately do not update root `updated_at`: memory evidence must not
        # masquerade as a human edit/render and invalidate approval concurrency.
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {"memory_check": snapshot}},
        )
        return snapshot

    async def index_published(self, run_id: str, approval: dict, external_post_urn: str | None) -> dict | None:
        if self.db is None:
            return None

        collection = self.db["content_runs"]
        existing = await collection.find_one({"run_id": run_id})
        if existing is None:
            return None

        final_content = approval.get("final_content") if isinstance(approval, dict) else None
        if not isinstance(final_content, str) or not final_content.strip():
            raise ValueError("Immutable approval final_content is required for published memory")

        workspace_id = existing.get("workspace_id") or LEGACY_WORKSPACE_ID
        identity = build_content_identity(final_content)
        indexed_at = _now()
        existing_check = existing.get("memory_check") if isinstance(existing.get("memory_check"), dict) else None

        try:
            published_memory = await self.repository.upsert(
                workspace_id=workspace_id,
                run_id=run_id,
                kind=ContentMemoryKind.PUBLISHED_CONTENT,
                text=final_content,
                content_status="PUBLISHED",
                external_post_urn=external_post_urn,
            )
            if published_memory is None:
                raise RuntimeError("Published content memory persistence is unavailable")

            if existing_check is None:
                snapshot = _published_base_snapshot(identity, indexed_at, status="READY")
                snapshot["published_memory_id"] = published_memory.memory_id
                await collection.update_one(
                    {"run_id": run_id},
                    {"$set": {"memory_check": snapshot}},
                )
            else:
                await collection.update_one(
                    {"run_id": run_id},
                    {"$set": {
                        "memory_check.published_memory_id": published_memory.memory_id,
                        "memory_check.published_index_status": "READY",
                        "memory_check.published_indexed_at": indexed_at,
                    }},
                )

            return {
                "status": "READY",
                "memory_id": published_memory.memory_id,
                "indexed_at": indexed_at,
            }
        except Exception as exc:
            error_message = str(exc)
            try:
                if existing_check is None:
                    snapshot = _published_base_snapshot(
                        identity,
                        indexed_at,
                        status="DEGRADED",
                        error_message=error_message,
                    )
                    await collection.update_one(
                        {"run_id": run_id},
                        {"$set": {"memory_check": snapshot}},
                    )
                else:
                    await collection.update_one(
                        {"run_id": run_id},
                        {"$set": {
                            "memory_check.published_index_status": "DEGRADED",
                            "memory_check.published_indexed_at": indexed_at,
                            "memory_check.error_message": error_message,
                        }},
                    )
            except Exception:
                # Publication truth is already external/local authority; the
                # advisory projection is not allowed to replace that truth.
                pass
            return {
                "status": "DEGRADED",
                "memory_id": None,
                "indexed_at": indexed_at,
                "error_message": error_message,
            }
