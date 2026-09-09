from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping, Any

from domain.jobs.models import (
    JobIntent,
    TransportMessage,
    deterministic_job_id,
    payload_digest,
    utc_now,
)
from domain.jobs.ports import JobHandler, JobOutboxRepository, JobTransport


@dataclass(frozen=True)
class ProcessOutcome:
    status: str
    job_id: str
    message_id: str


class JobCoordinator:
    """Durable Mongo-outbox to Redis transport coordinator.

    Redis messages are hints. Every side effect is gated by an authoritative
    Mongo claim and every duplicate delivery is resolved against that claim.
    """

    def __init__(
        self,
        *,
        repository: JobOutboxRepository,
        transport: JobTransport,
        lease_seconds: int = 30,
        max_execution_attempts: int = 3,
        rediscovery_seconds: int = 10,
    ):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if max_execution_attempts <= 0:
            raise ValueError("max_execution_attempts must be positive")
        if rediscovery_seconds < 0:
            raise ValueError("rediscovery_seconds must be non-negative")
        self.repository = repository
        self.transport = transport
        self.lease_seconds = lease_seconds
        self.max_execution_attempts = max_execution_attempts
        self.rediscovery_seconds = rediscovery_seconds

    async def enqueue(
        self,
        *,
        tenant_id: str,
        kind: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> JobIntent:
        tenant_id = tenant_id.strip()
        kind = kind.strip()
        idempotency_key = idempotency_key.strip()
        if not tenant_id or not kind or not idempotency_key:
            raise ValueError("tenant_id, kind and idempotency_key are required")
        digest = payload_digest(payload)
        job = JobIntent(
            tenant_id=tenant_id,
            job_id=deterministic_job_id(
                tenant_id=tenant_id,
                kind=kind,
                idempotency_key=idempotency_key,
                payload=payload,
            ),
            kind=kind,
            payload=dict(payload),
            payload_sha256=digest,
            created_at=utc_now(),
        )
        return await self.repository.create(job)

    async def dispatch_once(self, *, tenant_id: str, limit: int = 100) -> int:
        now = utc_now()
        jobs = await self.repository.list_dispatchable(
            tenant_id=tenant_id,
            now=now,
            rediscovery_before=now - timedelta(seconds=self.rediscovery_seconds),
            limit=max(1, limit),
        )
        dispatched = 0
        for job in jobs:
            await self.transport.publish(job)
            # Crash after XADD but before this write can duplicate delivery.
            # That is expected; authoritative execution claims absorb it.
            await self.repository.mark_dispatched(
                tenant_id=job.tenant_id,
                job_id=job.job_id,
                dispatched_at=utc_now(),
            )
            dispatched += 1
        return dispatched

    async def process_message(
        self,
        *,
        message: TransportMessage,
        worker_id: str,
        handler: JobHandler,
    ) -> ProcessOutcome:
        current = await self.repository.get(
            tenant_id=message.tenant_id,
            job_id=message.job_id,
        )
        if current is None:
            await self.transport.dead_letter(message, reason="missing Mongo job authority")
            await self.transport.ack(message.message_id)
            return ProcessOutcome("MISSING_AUTHORITY", message.job_id, message.message_id)

        if current.kind != message.kind or current.payload_sha256 != message.payload_sha256:
            await self.transport.dead_letter(message, reason="transport integrity mismatch")
            await self.transport.ack(message.message_id)
            return ProcessOutcome("INTEGRITY_MISMATCH", message.job_id, message.message_id)

        now = utc_now()
        claim = await self.repository.claim(
            tenant_id=message.tenant_id,
            job_id=message.job_id,
            worker_id=worker_id,
            lease_expires_at=now + timedelta(seconds=self.lease_seconds),
            now=now,
        )

        if claim.status in {"ALREADY_SUCCEEDED", "DEAD_LETTERED"}:
            await self.transport.ack(message.message_id)
            return ProcessOutcome(claim.status, message.job_id, message.message_id)

        if claim.status != "CLAIMED" or claim.job is None or not claim.claim_token:
            # BUSY is intentionally left pending. Another consumer owns the
            # authoritative lease; XAUTOCLAIM can recover it after expiry.
            return ProcessOutcome(claim.status, message.job_id, message.message_id)

        try:
            await handler(claim.job)
        except Exception as exc:
            failed = await self.repository.mark_failed(
                tenant_id=message.tenant_id,
                job_id=message.job_id,
                claim_token=claim.claim_token,
                error=f"{type(exc).__name__}: {exc}",
                failed_at=utc_now(),
            )
            if failed is None:
                return ProcessOutcome("CLAIM_LOST", message.job_id, message.message_id)

            if failed.execution_attempts >= self.max_execution_attempts:
                reason = failed.last_error or "execution attempts exhausted"
                dead = await self.repository.mark_dead_lettered(
                    tenant_id=message.tenant_id,
                    job_id=message.job_id,
                    error=reason,
                    failed_at=utc_now(),
                )
                if dead is not None:
                    await self.transport.dead_letter(message, reason=reason)
                await self.transport.ack(message.message_id)
                return ProcessOutcome("DEAD_LETTERED", message.job_id, message.message_id)

            # Transport delivery is complete even though business execution
            # failed. Mongo keeps the FAILED authority and dispatcher redrives.
            await self.transport.ack(message.message_id)
            return ProcessOutcome("FAILED_RETRYABLE", message.job_id, message.message_id)

        succeeded = await self.repository.mark_succeeded(
            tenant_id=message.tenant_id,
            job_id=message.job_id,
            claim_token=claim.claim_token,
            completed_at=utc_now(),
        )
        if not succeeded:
            return ProcessOutcome("CLAIM_LOST", message.job_id, message.message_id)

        await self.transport.ack(message.message_id)
        return ProcessOutcome("SUCCEEDED", message.job_id, message.message_id)

    async def consume_once(
        self,
        *,
        consumer: str,
        handler: JobHandler,
        count: int = 10,
        block_ms: int = 1000,
        recover_idle_ms: int | None = None,
    ) -> list[ProcessOutcome]:
        messages: list[TransportMessage] = []
        if recover_idle_ms is not None:
            messages.extend(
                await self.transport.recover_pending(
                    consumer=consumer,
                    min_idle_ms=max(0, recover_idle_ms),
                    count=count,
                )
            )
        remaining = max(0, count - len(messages))
        if remaining:
            messages.extend(
                await self.transport.read(
                    consumer=consumer,
                    count=remaining,
                    block_ms=block_ms,
                )
            )
        outcomes = []
        seen = set()
        for message in messages:
            if message.message_id in seen:
                continue
            seen.add(message.message_id)
            outcomes.append(
                await self.process_message(
                    message=message,
                    worker_id=consumer,
                    handler=handler,
                )
            )
        return outcomes

    async def lag_snapshot(self, *, tenant_id: str) -> dict[str, object]:
        now = utc_now()
        domain = await self.repository.lag_metrics(tenant_id=tenant_id, now=now)
        stream = await self.transport.lag_metrics()
        return {
            "tenant_id": tenant_id,
            "domain": {
                "dispatchable_count": domain.dispatchable_count,
                "ready_count": domain.ready_count,
                "claimed_count": domain.claimed_count,
                "failed_count": domain.failed_count,
                "dead_letter_count": domain.dead_letter_count,
                "oldest_dispatchable_age_seconds": domain.oldest_dispatchable_age_seconds,
            },
            "stream": {
                "stream_length": stream.stream_length,
                "pending_count": stream.pending_count,
                "lag": stream.lag,
            },
        }
