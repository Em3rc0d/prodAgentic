from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from domain.jobs.models import (
    ClaimResult,
    DispatchState,
    DomainLagMetrics,
    ExecutionState,
    JobIntent,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_doc(intent: JobIntent) -> dict[str, Any]:
    return {
        "tenant_id": intent.tenant_id,
        "job_id": intent.job_id,
        "kind": intent.kind,
        "payload": dict(intent.payload),
        "payload_sha256": intent.payload_sha256,
        "created_at": intent.created_at,
        "dispatch_state": intent.dispatch_state.value,
        "execution_state": intent.execution_state.value,
        "dispatch_attempts": intent.dispatch_attempts,
        "execution_attempts": intent.execution_attempts,
        "last_dispatched_at": intent.last_dispatched_at,
        "claimed_by": intent.claimed_by,
        "claim_token": intent.claim_token,
        "lease_expires_at": intent.lease_expires_at,
        "completed_at": intent.completed_at,
        "last_error": intent.last_error,
        "revision": intent.revision,
    }


def _from_doc(doc: dict[str, Any]) -> JobIntent:
    return JobIntent(
        tenant_id=doc["tenant_id"],
        job_id=doc["job_id"],
        kind=doc["kind"],
        payload=doc.get("payload") or {},
        payload_sha256=doc["payload_sha256"],
        created_at=_aware(doc["created_at"]),
        dispatch_state=DispatchState(doc.get("dispatch_state", DispatchState.PENDING.value)),
        execution_state=ExecutionState(doc.get("execution_state", ExecutionState.READY.value)),
        dispatch_attempts=int(doc.get("dispatch_attempts", 0)),
        execution_attempts=int(doc.get("execution_attempts", 0)),
        last_dispatched_at=_aware(doc.get("last_dispatched_at")),
        claimed_by=doc.get("claimed_by"),
        claim_token=doc.get("claim_token"),
        lease_expires_at=_aware(doc.get("lease_expires_at")),
        completed_at=_aware(doc.get("completed_at")),
        last_error=doc.get("last_error"),
        revision=int(doc.get("revision", 0)),
    )


class MongoJobOutboxRepository:
    """Mongo authority for durable dispatch intent and execution claims."""

    def __init__(self, db):
        self._collection = db["job_outbox"]
        self._indexes_ready = False
        self._index_lock = asyncio.Lock()

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        async with self._index_lock:
            if self._indexes_ready:
                return
            await self._collection.create_index(
                [("tenant_id", 1), ("job_id", 1)],
                unique=True,
                name="tenant_job_id_unique",
            )
            await self._collection.create_index(
                [
                    ("tenant_id", 1),
                    ("execution_state", 1),
                    ("last_dispatched_at", 1),
                    ("created_at", 1),
                ],
                name="tenant_job_dispatchable",
            )
            await self._collection.create_index(
                [("tenant_id", 1), ("execution_state", 1), ("lease_expires_at", 1)],
                name="tenant_job_claim_lease",
            )
            self._indexes_ready = True

    async def create(self, intent: JobIntent) -> JobIntent:
        await self._ensure_indexes()
        try:
            await self._collection.insert_one(_to_doc(intent))
            return intent
        except DuplicateKeyError:
            existing = await self.get(tenant_id=intent.tenant_id, job_id=intent.job_id)
            if existing is None:
                raise
            if (
                existing.kind != intent.kind
                or existing.payload_sha256 != intent.payload_sha256
                or dict(existing.payload) != dict(intent.payload)
            ):
                raise ValueError("deterministic job identity collision")
            return existing

    async def get(self, *, tenant_id: str, job_id: str) -> JobIntent | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"tenant_id": tenant_id, "job_id": job_id})
        return _from_doc(doc) if doc else None

    async def list_dispatchable(
        self,
        *,
        tenant_id: str,
        now: datetime,
        rediscovery_before: datetime,
        limit: int,
    ) -> list[JobIntent]:
        await self._ensure_indexes()
        query = {
            "tenant_id": tenant_id,
            "execution_state": {
                "$nin": [
                    ExecutionState.SUCCEEDED.value,
                    ExecutionState.DEAD_LETTERED.value,
                ]
            },
            "$or": [
                {"dispatch_state": DispatchState.PENDING.value},
                {"last_dispatched_at": None},
                {"last_dispatched_at": {"$lte": rediscovery_before}},
            ],
        }
        cursor = self._collection.find(query).sort([("created_at", 1), ("job_id", 1)]).limit(limit)
        return [_from_doc(doc) async for doc in cursor]

    async def mark_dispatched(
        self,
        *,
        tenant_id: str,
        job_id: str,
        dispatched_at: datetime,
    ) -> None:
        await self._ensure_indexes()
        await self._collection.update_one(
            {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "execution_state": {
                    "$nin": [
                        ExecutionState.SUCCEEDED.value,
                        ExecutionState.DEAD_LETTERED.value,
                    ]
                },
            },
            {
                "$set": {
                    "dispatch_state": DispatchState.DISPATCHED.value,
                    "last_dispatched_at": dispatched_at,
                },
                "$inc": {"dispatch_attempts": 1, "revision": 1},
            },
        )

    async def claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        worker_id: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> ClaimResult:
        await self._ensure_indexes()
        existing = await self.get(tenant_id=tenant_id, job_id=job_id)
        if existing is None:
            return ClaimResult(status="MISSING")
        if existing.execution_state is ExecutionState.SUCCEEDED:
            return ClaimResult(status="ALREADY_SUCCEEDED", job=existing)
        if existing.execution_state is ExecutionState.DEAD_LETTERED:
            return ClaimResult(status="DEAD_LETTERED", job=existing)

        claim_token = uuid4().hex
        doc = await self._collection.find_one_and_update(
            {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "$or": [
                    {"execution_state": ExecutionState.READY.value},
                    {"execution_state": ExecutionState.FAILED.value},
                    {
                        "execution_state": ExecutionState.CLAIMED.value,
                        "lease_expires_at": {"$lte": now},
                    },
                ],
            },
            {
                "$set": {
                    "execution_state": ExecutionState.CLAIMED.value,
                    "claimed_by": worker_id,
                    "claim_token": claim_token,
                    "lease_expires_at": lease_expires_at,
                    "last_error": None,
                },
                "$inc": {"execution_attempts": 1, "revision": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            current = await self.get(tenant_id=tenant_id, job_id=job_id)
            return ClaimResult(status="BUSY", job=current)
        claimed = _from_doc(doc)
        return ClaimResult(status="CLAIMED", job=claimed, claim_token=claim_token)

    async def mark_succeeded(
        self,
        *,
        tenant_id: str,
        job_id: str,
        claim_token: str,
        completed_at: datetime,
    ) -> bool:
        await self._ensure_indexes()
        result = await self._collection.update_one(
            {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "execution_state": ExecutionState.CLAIMED.value,
                "claim_token": claim_token,
            },
            {
                "$set": {
                    "execution_state": ExecutionState.SUCCEEDED.value,
                    "completed_at": completed_at,
                    "lease_expires_at": None,
                    "claimed_by": None,
                    "claim_token": None,
                    "last_error": None,
                },
                "$inc": {"revision": 1},
            },
        )
        return result.modified_count == 1

    async def mark_failed(
        self,
        *,
        tenant_id: str,
        job_id: str,
        claim_token: str,
        error: str,
        failed_at: datetime,
    ) -> JobIntent | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one_and_update(
            {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "execution_state": ExecutionState.CLAIMED.value,
                "claim_token": claim_token,
            },
            {
                "$set": {
                    "execution_state": ExecutionState.FAILED.value,
                    "last_error": error[:1000],
                    "lease_expires_at": None,
                    "claimed_by": None,
                    "claim_token": None,
                    "last_dispatched_at": failed_at,
                },
                "$inc": {"revision": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return _from_doc(doc) if doc else None

    async def mark_dead_lettered(
        self,
        *,
        tenant_id: str,
        job_id: str,
        error: str,
        failed_at: datetime,
    ) -> JobIntent | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one_and_update(
            {
                "tenant_id": tenant_id,
                "job_id": job_id,
                "execution_state": {
                    "$nin": [
                        ExecutionState.SUCCEEDED.value,
                        ExecutionState.DEAD_LETTERED.value,
                    ]
                },
            },
            {
                "$set": {
                    "execution_state": ExecutionState.DEAD_LETTERED.value,
                    "last_error": error[:1000],
                    "completed_at": None,
                    "lease_expires_at": None,
                    "claimed_by": None,
                    "claim_token": None,
                },
                "$inc": {"revision": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return _from_doc(doc) if doc else None

    async def lag_metrics(self, *, tenant_id: str, now: datetime) -> DomainLagMetrics:
        await self._ensure_indexes()
        base = {"tenant_id": tenant_id}
        dispatchable = {
            **base,
            "execution_state": {
                "$nin": [
                    ExecutionState.SUCCEEDED.value,
                    ExecutionState.DEAD_LETTERED.value,
                ]
            },
        }
        counts = {}
        for state in (
            ExecutionState.READY,
            ExecutionState.CLAIMED,
            ExecutionState.FAILED,
            ExecutionState.DEAD_LETTERED,
        ):
            counts[state] = await self._collection.count_documents(
                {**base, "execution_state": state.value}
            )
        dispatchable_count = await self._collection.count_documents(dispatchable)
        oldest = await self._collection.find_one(dispatchable, sort=[("created_at", 1)])
        age = 0.0
        if oldest:
            created = _aware(oldest["created_at"])
            age = max(0.0, (now - created).total_seconds())
        return DomainLagMetrics(
            dispatchable_count=dispatchable_count,
            ready_count=counts[ExecutionState.READY],
            claimed_count=counts[ExecutionState.CLAIMED],
            failed_count=counts[ExecutionState.FAILED],
            dead_letter_count=counts[ExecutionState.DEAD_LETTERED],
            oldest_dispatchable_age_seconds=age,
        )
