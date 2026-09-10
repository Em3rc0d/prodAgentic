from __future__ import annotations

from domain.jobs.models import DispatchState, ExecutionState
from infrastructure.mongo.jobs import MongoJobOutboxRepository, _from_doc


class MongoPublishJobOutboxRepository(MongoJobOutboxRepository):
    """S10 view over S9 outbox that dispatches only LinkedIn publication jobs.

    S9 remains the durable authority/claim implementation. This specialization
    prevents unrelated future render/analytics intents from being XADDed to the
    dedicated pa:publish:v1 stream.
    """

    JOB_KIND = "publish.linkedin.v1"

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
