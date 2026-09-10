from __future__ import annotations

from domain.jobs.models import DispatchState, ExecutionState
from infrastructure.mongo.jobs import MongoJobOutboxRepository, _from_doc


class MongoAnalyticsJobOutboxRepository(MongoJobOutboxRepository):
    """S11 specialization that dispatches only LinkedIn analytics jobs."""

    JOB_KIND = "analytics.linkedin.v1"

    async def list_dispatchable(self, *, tenant_id, now, rediscovery_before, limit):
        await self._ensure_indexes()
        query = {
            "tenant_id": tenant_id,
            "kind": self.JOB_KIND,
            "execution_state": {
                "$nin": [ExecutionState.SUCCEEDED.value, ExecutionState.DEAD_LETTERED.value]
            },
            "$or": [
                {"dispatch_state": DispatchState.PENDING.value},
                {"last_dispatched_at": None},
                {"last_dispatched_at": {"$lte": rediscovery_before}},
            ],
        }
        cursor = self._collection.find(query).sort([("created_at", 1), ("job_id", 1)]).limit(limit)
        return [_from_doc(doc) async for doc in cursor]
