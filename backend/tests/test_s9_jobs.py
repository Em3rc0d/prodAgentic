from __future__ import annotations

import os
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from application.jobs.service import JobCoordinator
from domain.jobs.models import (
    ExecutionState,
    StreamLagMetrics,
    TransportMessage,
    deterministic_job_id,
    payload_digest,
)
from infrastructure.mongo.jobs import MongoJobOutboxRepository
from infrastructure.redis.streams import RedisStreamsSettings, RedisStreamsTransport


class RecordingTransport:
    def __init__(self):
        self.published = []
        self.acked = []
        self.dead_letters = []

    async def ensure_group(self):
        return None

    async def publish(self, job):
        self.published.append(job.job_id)
        return f"{len(self.published)}-0"

    async def read(self, **kwargs):
        return []

    async def recover_pending(self, **kwargs):
        return []

    async def ack(self, message_id):
        self.acked.append(message_id)

    async def dead_letter(self, message, *, reason):
        self.dead_letters.append((message.job_id, reason))
        return f"dlq-{len(self.dead_letters)}-0"

    async def lag_metrics(self):
        return StreamLagMetrics(stream_length=0, pending_count=0, lag=0)

    async def close(self):
        return None


async def _mongo_repo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db_name = f"prodagentic_s9_{uuid4().hex}"
    db = client[db_name]
    return client, db, MongoJobOutboxRepository(db)


def test_s9_job_identity_binds_tenant_kind_payload_and_idempotency_key():
    payload = {"approval_id": "approval-1", "asset_sha256": "a" * 64}
    baseline = deterministic_job_id(
        tenant_id="tenant-a",
        kind="publish",
        idempotency_key="approval-1",
        payload=payload,
    )
    assert baseline == deterministic_job_id(
        tenant_id="tenant-a",
        kind="publish",
        idempotency_key="approval-1",
        payload=dict(reversed(list(payload.items()))),
    )
    assert baseline != deterministic_job_id(
        tenant_id="tenant-b",
        kind="publish",
        idempotency_key="approval-1",
        payload=payload,
    )
    assert baseline != deterministic_job_id(
        tenant_id="tenant-a",
        kind="render",
        idempotency_key="approval-1",
        payload=payload,
    )
    assert payload_digest(payload) == payload_digest(dict(reversed(list(payload.items()))))


@pytest.mark.asyncio
async def test_s9_duplicate_delivery_executes_side_effect_once_via_mongo_claim():
    client, db, repo = await _mongo_repo()
    transport = RecordingTransport()
    coordinator = JobCoordinator(repository=repo, transport=transport, rediscovery_seconds=0)
    calls = []
    try:
        job = await coordinator.enqueue(
            tenant_id="tenant-a",
            kind="test.side-effect",
            idempotency_key="once",
            payload={"value": 1},
        )
        message_a = TransportMessage(
            message_id="1-0",
            tenant_id=job.tenant_id,
            job_id=job.job_id,
            kind=job.kind,
            payload_sha256=job.payload_sha256,
        )
        message_b = TransportMessage(
            message_id="2-0",
            tenant_id=job.tenant_id,
            job_id=job.job_id,
            kind=job.kind,
            payload_sha256=job.payload_sha256,
        )

        async def handler(claimed):
            calls.append(claimed.job_id)

        first = await coordinator.process_message(
            message=message_a,
            worker_id="worker-a",
            handler=handler,
        )
        second = await coordinator.process_message(
            message=message_b,
            worker_id="worker-b",
            handler=handler,
        )
        current = await repo.get(tenant_id=job.tenant_id, job_id=job.job_id)

        assert first.status == "SUCCEEDED"
        assert second.status == "ALREADY_SUCCEEDED"
        assert calls == [job.job_id]
        assert transport.acked == ["1-0", "2-0"]
        assert current is not None
        assert current.execution_state is ExecutionState.SUCCEEDED
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_s9_dead_letter_is_terminal_failure_never_business_success():
    client, db, repo = await _mongo_repo()
    transport = RecordingTransport()
    coordinator = JobCoordinator(
        repository=repo,
        transport=transport,
        max_execution_attempts=1,
        rediscovery_seconds=0,
    )
    try:
        job = await coordinator.enqueue(
            tenant_id="tenant-a",
            kind="test.fail",
            idempotency_key="fail",
            payload={"value": 2},
        )
        message = TransportMessage(
            message_id="1-0",
            tenant_id=job.tenant_id,
            job_id=job.job_id,
            kind=job.kind,
            payload_sha256=job.payload_sha256,
        )

        async def failing_handler(_):
            raise RuntimeError("expected failure")

        outcome = await coordinator.process_message(
            message=message,
            worker_id="worker-a",
            handler=failing_handler,
        )
        current = await repo.get(tenant_id=job.tenant_id, job_id=job.job_id)

        assert outcome.status == "DEAD_LETTERED"
        assert current is not None
        assert current.execution_state is ExecutionState.DEAD_LETTERED
        assert current.completed_at is None
        assert len(transport.dead_letters) == 1
        assert transport.acked == ["1-0"]
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_s9_real_redis_loss_redrive_pending_recovery_duplicates_and_lag():
    if os.getenv("S9_REDIS_INTEGRATION", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("S9 real Redis integration is certified by s9-cert workflow")

    client, db, repo = await _mongo_repo()
    suffix = uuid4().hex
    settings = RedisStreamsSettings(
        url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        stream=f"prodagentic:s9:test:{suffix}",
        group=f"s9-test-group-{suffix}",
        dead_letter_stream=f"prodagentic:s9:dlq:{suffix}",
    )
    transport = RedisStreamsTransport(settings)
    coordinator = JobCoordinator(
        repository=repo,
        transport=transport,
        rediscovery_seconds=0,
        lease_seconds=1,
    )
    side_effects = []
    try:
        assert await transport.ping()
        await transport.ensure_group()

        pending_job = await coordinator.enqueue(
            tenant_id="tenant-real",
            kind="test.pending-recovery",
            idempotency_key="pending",
            payload={"approval_id": "a1"},
        )
        assert await coordinator.dispatch_once(tenant_id="tenant-real") == 1

        abandoned = await transport.read(consumer="consumer-a", block_ms=50)
        assert len(abandoned) == 1
        recovered = await transport.recover_pending(
            consumer="consumer-b",
            min_idle_ms=0,
            count=10,
        )
        assert [message.job_id for message in recovered] == [pending_job.job_id]

        async def handler(job):
            side_effects.append(job.job_id)

        recovered_outcome = await coordinator.process_message(
            message=recovered[0],
            worker_id="consumer-b",
            handler=handler,
        )
        assert recovered_outcome.status == "SUCCEEDED"

        await transport.publish(pending_job)
        duplicate = await transport.read(consumer="consumer-c", block_ms=50)
        assert len(duplicate) == 1
        duplicate_outcome = await coordinator.process_message(
            message=duplicate[0],
            worker_id="consumer-c",
            handler=handler,
        )
        assert duplicate_outcome.status == "ALREADY_SUCCEEDED"
        assert side_effects == [pending_job.job_id]

        loss_job = await coordinator.enqueue(
            tenant_id="tenant-real",
            kind="test.redis-loss",
            idempotency_key="redis-loss",
            payload={"approval_id": "a2"},
        )
        assert await coordinator.dispatch_once(tenant_id="tenant-real") >= 1
        await transport._command("DEL", settings.stream)
        await transport.ensure_group()

        assert await coordinator.dispatch_once(tenant_id="tenant-real") >= 1
        redriven = await transport.read(consumer="consumer-d", count=10, block_ms=50)
        loss_messages = [message for message in redriven if message.job_id == loss_job.job_id]
        assert loss_messages
        loss_outcome = await coordinator.process_message(
            message=loss_messages[0],
            worker_id="consumer-d",
            handler=handler,
        )
        assert loss_outcome.status == "SUCCEEDED"

        snapshot = await coordinator.lag_snapshot(tenant_id="tenant-real")
        assert snapshot["domain"]["dispatchable_count"] >= 0
        assert snapshot["stream"]["stream_length"] >= 0
        assert snapshot["stream"]["pending_count"] >= 0
    finally:
        try:
            await transport._command("DEL", settings.stream, settings.dead_letter_stream)
        except Exception:
            pass
        await transport.close()
        await client.drop_database(db.name)
        client.close()
