from __future__ import annotations

import asyncio
import os

from application.jobs.service import JobCoordinator
from application.publishing.legacy_bridge import migrate_legacy_linkedin_connection
from application.publishing.service import (
    PreparedPublicationBuilder,
    PublishWorkerHandler,
    ScheduleDispatcher,
)
from application.tenancy.context import tenant_context_for_actor
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.linkedin.adapter import LinkedInPlatformAdapter
from infrastructure.mongo.approval import MongoApprovalRepository
from infrastructure.mongo.publish_jobs import MongoPublishJobOutboxRepository
from infrastructure.mongo.publishing import (
    MongoConnectionRepository,
    MongoPublicationRepository,
    MongoScheduleRepository,
)
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.rendering import MongoRenderingRepository
from infrastructure.redis.streams import RedisStreamsSettings, RedisStreamsTransport


def _transport() -> RedisStreamsTransport:
    base = RedisStreamsSettings.from_env()
    return RedisStreamsTransport(
        RedisStreamsSettings(
            url=base.url,
            stream=os.getenv("PRODAGENTIC_PUBLISH_STREAM", "pa:publish:v1"),
            group=os.getenv("PRODAGENTIC_PUBLISH_GROUP", "pa-publish-workers-v1"),
            dead_letter_stream=os.getenv("PRODAGENTIC_PUBLISH_DLQ_STREAM", "pa:publish:v1:dead"),
            connect_timeout_seconds=base.connect_timeout_seconds,
        )
    )


async def s10_publish_loop(db) -> None:
    """Own S10 scheduling/publication side effects while MK1_PUBLISH_WORKER is enabled."""

    context = tenant_context_for_actor("s10-publish-cell", actor_type="worker")
    await migrate_legacy_linkedin_connection(db)

    schedules = MongoScheduleRepository(db, context)
    publications = MongoPublicationRepository(db, context)
    connections = MongoConnectionRepository(db, context)
    jobs = MongoPublishJobOutboxRepository(db)
    transport = _transport()
    coordinator = JobCoordinator(
        repository=jobs,
        transport=transport,
        lease_seconds=max(5, int(os.getenv("S10_JOB_LEASE_SECONDS", "30"))),
        max_execution_attempts=max(1, int(os.getenv("S10_JOB_MAX_ATTEMPTS", "3"))),
        rediscovery_seconds=max(0, int(os.getenv("S10_JOB_REDISCOVERY_SECONDS", "10"))),
    )
    adapter = LinkedInPlatformAdapter()
    builder = PreparedPublicationBuilder(
        approvals=MongoApprovalRepository(db, context),
        production=MongoProductionRepository(db, context),
        rendering=MongoRenderingRepository(db, context),
        asset_store=FilesystemAssetStore(),
    )
    dispatcher = ScheduleDispatcher(
        schedules=schedules,
        publications=publications,
        connections=connections,
        jobs=coordinator,
    )
    handler = PublishWorkerHandler(
        publications=publications,
        schedules=schedules,
        connections=connections,
        builder=builder,
        adapter=adapter,
    )
    poll_seconds = max(0.25, float(os.getenv("S10_PUBLISH_POLL_SECONDS", "2")))
    recover_idle_ms = max(1000, int(os.getenv("S10_PUBLISH_RECOVER_IDLE_MS", "30000")))

    try:
        await transport.ensure_group()
        while True:
            try:
                await dispatcher.dispatch_due(tenant_id=context.tenant_id)
                await coordinator.dispatch_once(tenant_id=context.tenant_id)
                await coordinator.consume_once(
                    consumer=f"publish-{os.getpid()}",
                    handler=handler,
                    count=10,
                    block_ms=100,
                    recover_idle_ms=recover_idle_ms,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Durable Mongo authority remains intact; the next loop recovers.
                print(f"[WARN] S10 publish cell iteration failed safely: {type(exc).__name__}: {exc}")
            await asyncio.sleep(poll_seconds)
    finally:
        await transport.close()
