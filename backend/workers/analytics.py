from __future__ import annotations

import asyncio
import os

from application.analytics.service import AnalyticsIntentPlanner, AnalyticsWorkerHandler
from application.jobs.service import JobCoordinator
from application.tenancy.context import tenant_context_for_actor
from infrastructure.linkedin.analytics import LinkedInAnalyticsAdapter
from infrastructure.mongo.analytics import MongoMetricSnapshotRepository
from infrastructure.mongo.analytics_jobs import MongoAnalyticsJobOutboxRepository
from infrastructure.mongo.analytics_publications import MongoPublishedPublicationAnalyticsReader
from infrastructure.mongo.publishing import MongoConnectionRepository
from infrastructure.redis.streams import RedisStreamsSettings, RedisStreamsTransport


def _transport() -> RedisStreamsTransport:
    base = RedisStreamsSettings.from_env()
    return RedisStreamsTransport(
        RedisStreamsSettings(
            url=base.url,
            stream=os.getenv("PRODAGENTIC_ANALYTICS_STREAM", "pa:analytics:v1"),
            group=os.getenv("PRODAGENTIC_ANALYTICS_GROUP", "pa-analytics-workers-v1"),
            dead_letter_stream=os.getenv("PRODAGENTIC_ANALYTICS_DLQ_STREAM", "pa:analytics:v1:dead"),
            connect_timeout_seconds=base.connect_timeout_seconds,
        )
    )


async def s11_analytics_loop(db) -> None:
    """Collect append-only provider observations while MK1_ANALYTICS_WORKER is enabled."""

    context = tenant_context_for_actor("s11-analytics-cell", actor_type="worker")
    publications = MongoPublishedPublicationAnalyticsReader(db, context)
    connections = MongoConnectionRepository(db, context)
    snapshots = MongoMetricSnapshotRepository(db, context)
    jobs = MongoAnalyticsJobOutboxRepository(db)
    transport = _transport()
    coordinator = JobCoordinator(
        repository=jobs,
        transport=transport,
        lease_seconds=max(5, int(os.getenv("S11_JOB_LEASE_SECONDS", "30"))),
        max_execution_attempts=max(1, int(os.getenv("S11_JOB_MAX_ATTEMPTS", "5"))),
        rediscovery_seconds=max(0, int(os.getenv("S11_JOB_REDISCOVERY_SECONDS", "15"))),
    )
    adapter = LinkedInAnalyticsAdapter()
    planner = AnalyticsIntentPlanner(
        publications=publications,
        connections=connections,
        snapshots=snapshots,
        adapter=adapter,
        jobs=coordinator,
    )
    handler = AnalyticsWorkerHandler(
        publications=publications,
        connections=connections,
        snapshots=snapshots,
        adapter=adapter,
    )
    poll_seconds = max(1.0, float(os.getenv("S11_ANALYTICS_POLL_SECONDS", "30")))
    recover_idle_ms = max(1000, int(os.getenv("S11_ANALYTICS_RECOVER_IDLE_MS", "30000")))

    try:
        await transport.ensure_group()
        while True:
            try:
                await planner.enqueue_due(tenant_id=context.tenant_id)
                await coordinator.dispatch_once(tenant_id=context.tenant_id)
                await coordinator.consume_once(
                    consumer=f"analytics-{os.getpid()}",
                    handler=handler,
                    count=10,
                    block_ms=100,
                    recover_idle_ms=recover_idle_ms,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Mongo Publication/outbox/snapshot authority remains durable.
                print(f"[WARN] S11 analytics cell iteration failed safely: {type(exc).__name__}: {exc}")
            await asyncio.sleep(poll_seconds)
    finally:
        await transport.close()
