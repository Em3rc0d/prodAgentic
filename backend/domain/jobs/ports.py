from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable, Protocol

from domain.jobs.models import (
    ClaimResult,
    DomainLagMetrics,
    JobIntent,
    StreamLagMetrics,
    TransportMessage,
)


class JobOutboxRepository(Protocol):
    async def create(self, intent: JobIntent) -> JobIntent: ...

    async def get(self, *, tenant_id: str, job_id: str) -> JobIntent | None: ...

    async def list_dispatchable(
        self,
        *,
        tenant_id: str,
        now: datetime,
        rediscovery_before: datetime,
        limit: int,
    ) -> list[JobIntent]: ...

    async def mark_dispatched(
        self,
        *,
        tenant_id: str,
        job_id: str,
        dispatched_at: datetime,
    ) -> None: ...

    async def claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        worker_id: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> ClaimResult: ...

    async def mark_succeeded(
        self,
        *,
        tenant_id: str,
        job_id: str,
        claim_token: str,
        completed_at: datetime,
    ) -> bool: ...

    async def mark_failed(
        self,
        *,
        tenant_id: str,
        job_id: str,
        claim_token: str,
        error: str,
        failed_at: datetime,
    ) -> JobIntent | None: ...

    async def mark_dead_lettered(
        self,
        *,
        tenant_id: str,
        job_id: str,
        error: str,
        failed_at: datetime,
    ) -> JobIntent | None: ...

    async def lag_metrics(self, *, tenant_id: str, now: datetime) -> DomainLagMetrics: ...


class JobTransport(Protocol):
    async def ensure_group(self) -> None: ...

    async def publish(self, job: JobIntent) -> str: ...

    async def read(
        self,
        *,
        consumer: str,
        count: int = 1,
        block_ms: int = 1000,
    ) -> list[TransportMessage]: ...

    async def recover_pending(
        self,
        *,
        consumer: str,
        min_idle_ms: int,
        count: int = 10,
    ) -> list[TransportMessage]: ...

    async def ack(self, message_id: str) -> None: ...

    async def dead_letter(self, message: TransportMessage, *, reason: str) -> str: ...

    async def lag_metrics(self) -> StreamLagMetrics: ...

    async def close(self) -> None: ...


JobHandler = Callable[[JobIntent], Awaitable[None]]
