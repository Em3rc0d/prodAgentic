from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING

from domain.publishing.models import PublicationState, PublicationV1
from domain.tenants.models import TenantContext


def _aware(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {key: _aware(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_aware(item) for item in value]
    return value


def _clean(document: dict | None) -> dict | None:
    if not document:
        return None
    return _aware({key: value for key, value in document.items() if key != "_id"})


class MongoPublishedPublicationAnalyticsReader:
    """Read-only S11 projection over the certified S10 PublicationV1 authority."""

    def __init__(self, db, context: TenantContext):
        self.context = context
        self.collection = db["publications_v2"]

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    async def get_published(self, publication_id: str) -> PublicationV1 | None:
        raw = await self.collection.find_one(
            self._scope(
                {
                    "publication_id": publication_id,
                    "state": PublicationState.PUBLISHED.value,
                }
            )
        )
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def list_published(self, *, limit: int = 250) -> list[PublicationV1]:
        bounded = max(1, min(int(limit), 5000))
        cursor = (
            self.collection.find(self._scope({"state": PublicationState.PUBLISHED.value}))
            .sort([("completed_at", ASCENDING), ("publication_id", ASCENDING)])
            .limit(bounded)
        )
        return [PublicationV1.model_validate(_clean(raw)) async for raw in cursor]

    async def count_published(self) -> int:
        return await self.collection.count_documents(
            self._scope({"state": PublicationState.PUBLISHED.value})
        )
