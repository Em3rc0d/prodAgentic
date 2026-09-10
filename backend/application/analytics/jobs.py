from __future__ import annotations

from typing import Any, Mapping

from domain.jobs.models import JobIntent, deterministic_job_id, payload_digest, utc_now


class AnalyticsJobEnqueuer:
    """Create durable analytics intents without opening Redis from HTTP routes."""

    def __init__(self, repository):
        self.repository = repository

    async def enqueue(
        self,
        *,
        tenant_id: str,
        kind: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> JobIntent:
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
