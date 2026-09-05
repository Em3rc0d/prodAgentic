from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from domain.planning.models import Batch, ContentItem, EditorialMemoryEntry, PersistedContentPlan
from domain.planning.trace import BatchPlanningTraceV1
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return value


class MongoPlanningRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.batches = TenantScopedMongoRepository(db, "batches", context)
        self.items = TenantScopedMongoRepository(db, "content_items", context)
        self.plans = TenantScopedMongoRepository(db, "content_plans", context)
        self.memory = TenantScopedMongoRepository(db, "editorial_memory", context)
        self.traces = TenantScopedMongoRepository(db, "planning_traces", context)

    async def list_recent_memory(self, profile_id: str, since: datetime) -> list[EditorialMemoryEntry]:
        documents = await self.memory.find_many(
            {"profile_id": profile_id, "effective_at": {"$gte": since}},
            sort=[("effective_at", -1)],
        )
        return [EditorialMemoryEntry.model_validate(_clean(document)) for document in documents]

    async def replace_projected_memory(
        self,
        profile_id: str,
        entries: list[EditorialMemoryEntry],
        source_prefix: str,
    ) -> None:
        if not source_prefix or not re.fullmatch(r"[a-z0-9_-]+", source_prefix):
            raise ValueError("source_prefix must be a safe stable identifier")
        await self.memory.delete_many(
            {"profile_id": profile_id, "memory_id": {"$regex": f"^{re.escape(source_prefix)}"}}
        )
        for entry in entries:
            if entry.profile_id != profile_id:
                raise ValueError("projected memory profile mismatch")
            await self.memory.insert_one(entry.model_dump())

    async def save_batch(
        self,
        batch: Batch,
        items: list[ContentItem],
        plans: list[PersistedContentPlan],
        trace: BatchPlanningTraceV1,
    ) -> None:
        if any(item.batch_id != batch.batch_id for item in items):
            raise ValueError("ContentItem batch mismatch")
        if any(plan.batch_id != batch.batch_id for plan in plans):
            raise ValueError("ContentPlan batch mismatch")
        if trace.batch_id != batch.batch_id:
            raise ValueError("Planning trace batch mismatch")
        if len(items) != len(plans):
            raise ValueError("Every selected ContentItem requires one persisted ContentPlan")

        inserted_items: list[str] = []
        inserted_plans: list[str] = []
        trace_inserted = False
        batch_inserted = False
        try:
            # Batch is the visibility/commit marker. Evidence is written first so
            # a visible Batch never points at missing selected-plan evidence after
            # an ordinary adapter failure.
            await self.traces.insert_one(trace.model_dump())
            trace_inserted = True
            for plan in plans:
                await self.plans.insert_one(plan.model_dump())
                inserted_plans.append(plan.artifact_id)
            for item in items:
                await self.items.insert_one(item.model_dump())
                inserted_items.append(item.content_id)
            await self.batches.insert_one(batch.model_dump())
            batch_inserted = True
        except Exception:
            # Normal failures are compensated. A hard process death may leave
            # orphan pre-commit evidence, but because Batch is written last it
            # cannot masquerade as a committed Batch. Cleanup/rebuild remains
            # safe because these artifacts carry tenant + batch identity.
            if batch_inserted:
                await self.batches.delete_one({"batch_id": batch.batch_id})
            for content_id in inserted_items:
                await self.items.delete_one({"content_id": content_id})
            for artifact_id in inserted_plans:
                await self.plans.delete_one({"artifact_id": artifact_id})
            if trace_inserted:
                await self.traces.delete_one({"batch_id": batch.batch_id})
            raise

    async def get_batch(self, batch_id: str) -> Batch | None:
        document = _clean(await self.batches.find_one({"batch_id": batch_id}))
        return Batch.model_validate(document) if document else None

    async def list_batch_items(self, batch_id: str) -> list[ContentItem]:
        documents = await self.items.find_many({"batch_id": batch_id}, sort=[("created_at", 1)])
        return [ContentItem.model_validate(_clean(document)) for document in documents]

    async def list_batch_plans(self, batch_id: str) -> list[PersistedContentPlan]:
        documents = await self.plans.find_many({"batch_id": batch_id}, sort=[("created_at", 1)])
        return [PersistedContentPlan.model_validate(_clean(document)) for document in documents]

    async def get_planning_trace(self, batch_id: str) -> BatchPlanningTraceV1 | None:
        document = _clean(await self.traces.find_one({"batch_id": batch_id}))
        return BatchPlanningTraceV1.model_validate(document) if document else None
