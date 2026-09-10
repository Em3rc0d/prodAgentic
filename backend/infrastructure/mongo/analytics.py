from __future__ import annotations

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from domain.analytics.models import MetricSnapshotV1, canonical_sha256
from domain.tenants.models import TenantContext


class MetricSnapshotConflict(RuntimeError):
    pass


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class MongoMetricSnapshotRepository:
    """Tenant-scoped append-only MetricSnapshotV1 authority."""

    def __init__(self, db, context: TenantContext):
        self.context = context
        self.collection = db["metric_snapshots_v1"]

    async def ensure_indexes(self):
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("metric_snapshot_id", ASCENDING)],
            unique=True,
            name="tenant_metric_snapshot_unique",
        )
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("operation_key", ASCENDING)],
            unique=True,
            name="tenant_metric_operation_unique",
        )
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("publication_id", ASCENDING), ("captured_at", DESCENDING)],
            name="tenant_publication_metric_history",
        )
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("provider", ASCENDING), ("captured_at", DESCENDING)],
            name="tenant_provider_metric_history",
        )

    @staticmethod
    def _document(snapshot: MetricSnapshotV1) -> dict:
        return snapshot.model_dump(mode="python")

    @staticmethod
    def _model(document: dict | None) -> MetricSnapshotV1 | None:
        if not document:
            return None
        payload = {key: value for key, value in document.items() if key != "_id"}
        return MetricSnapshotV1.model_validate(payload)

    async def append(self, snapshot: MetricSnapshotV1) -> MetricSnapshotV1:
        if snapshot.tenant_id != self.context.tenant_id:
            raise ValueError("MetricSnapshot tenant does not match repository context")
        await self.ensure_indexes()
        try:
            await self.collection.insert_one(self._document(snapshot))
            return snapshot
        except DuplicateKeyError:
            existing = await self.get_by_operation_key(snapshot.operation_key)
            if existing is None:
                existing = await self.get(snapshot.metric_snapshot_id)
            if existing is not None and canonical_sha256(existing) == canonical_sha256(snapshot):
                return existing
            raise MetricSnapshotConflict(
                "MetricSnapshot deterministic identity already exists with different evidence"
            )

    async def get(self, metric_snapshot_id: str) -> MetricSnapshotV1 | None:
        document = await self.collection.find_one(
            {"tenant_id": self.context.tenant_id, "metric_snapshot_id": metric_snapshot_id}
        )
        return self._model(document)

    async def get_by_operation_key(self, operation_key: str) -> MetricSnapshotV1 | None:
        document = await self.collection.find_one(
            {"tenant_id": self.context.tenant_id, "operation_key": operation_key}
        )
        return self._model(document)

    async def list_for_publication(
        self,
        publication_id: str,
        *,
        limit: int = 100,
    ) -> list[MetricSnapshotV1]:
        bounded_limit = max(1, min(int(limit), 500))
        cursor = self.collection.find(
            {"tenant_id": self.context.tenant_id, "publication_id": publication_id}
        ).sort("captured_at", DESCENDING).limit(bounded_limit)
        return [self._model(document) async for document in cursor]

    async def list_recent(self, *, limit: int = 1000) -> list[MetricSnapshotV1]:
        bounded_limit = max(1, min(int(limit), 5000))
        cursor = self.collection.find(
            {"tenant_id": self.context.tenant_id}
        ).sort("captured_at", DESCENDING).limit(bounded_limit)
        return [self._model(document) async for document in cursor]

    async def latest_captured_at(self) -> datetime | None:
        document = await self.collection.find_one(
            {"tenant_id": self.context.tenant_id},
            sort=[("captured_at", DESCENDING)],
            projection={"captured_at": 1},
        )
        if not document:
            return None
        return _as_utc(document.get("captured_at"))
