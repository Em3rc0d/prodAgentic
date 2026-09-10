from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from application.jobs.service import JobCoordinator
from application.publishing.legacy_bridge import migrate_legacy_linkedin_connection
from application.publishing.service import PreparedPublicationBuilder, PublishWorkerHandler
from application.tenancy.context import bootstrap_tenant_id
from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.approval.models import ApprovalAssetV2, ApprovalBundleV2, canonical_approval_sha256
from domain.jobs.models import StreamLagMetrics, TransportMessage
from domain.production.models import ContentSpecV1, TextFormatSpecV1, canonical_sha256 as production_sha256
from domain.publishing.models import (
    PlatformCapabilityV1,
    PublicationReceiptV1,
    PublicationState,
    PublicationV1,
    ScheduleState,
    ScheduleV1,
    canonical_sha256,
    deterministic_publication_id,
    publication_operation_key,
)
from domain.rendering.models import RenderContentType
from domain.tenants.models import TenantContext
from infrastructure.linkedin.adapter import (
    LinkedInPlatformAdapter,
    PlatformSafeFailure,
    PlatformUncertainFailure,
    PreparedPublication,
)
from infrastructure.mongo.publish_jobs import MongoPublishJobOutboxRepository
from infrastructure.mongo.publishing import (
    MongoConnectionRepository,
    MongoPublicationRepository,
    MongoScheduleRepository,
)
from infrastructure.redis.streams import RedisStreamsSettings, RedisStreamsTransport


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_s10_{uuid4().hex}"]
    return client, db


def _context(tenant: str = "tenant-s10") -> TenantContext:
    return TenantContext(tenant_id=tenant, actor_id="s10-test", actor_type="worker")


def _publication(*, tenant: str = "tenant-s10", state: PublicationState = PublicationState.PENDING) -> PublicationV1:
    key = publication_operation_key(
        tenant_id=tenant,
        approval_id="approval-s10",
        bundle_sha256="a" * 64,
        provider="linkedin",
        external_identity="urn:li:person:123",
        destination="member_feed|urn:li:person:123",
    )
    return PublicationV1(
        publication_id=deterministic_publication_id(key),
        tenant_id=tenant,
        approval_id="approval-s10",
        schedule_id="schedule-s10",
        connection_id="conn-s10",
        destination="member_feed|urn:li:person:123",
        state=state,
        idempotency_key=key,
        bundle_sha256="a" * 64,
    )


def _receipt(post_id: str = "urn:li:share:1") -> PublicationReceiptV1:
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": 1,
        "provider": "linkedin",
        "external_post_id": post_id,
        "external_asset_ids": (),
        "provider_api_version": "202608",
        "received_at": now,
    }
    return PublicationReceiptV1(**payload, receipt_digest=canonical_sha256(payload))


class RecordingTransport:
    def __init__(self):
        self.acked: list[str] = []
        self.dead: list[str] = []

    async def ensure_group(self): return None
    async def publish(self, job): return "1-0"
    async def read(self, **kwargs): return []
    async def recover_pending(self, **kwargs): return []
    async def ack(self, message_id): self.acked.append(message_id)
    async def dead_letter(self, message, *, reason): self.dead.append(reason); return "dead-1-0"
    async def lag_metrics(self): return StreamLagMetrics(stream_length=0, pending_count=0, lag=0)
    async def close(self): return None


class CountingAdapter:
    def __init__(self):
        self.calls = 0

    async def capabilities(self, connection):
        return PlatformCapabilityV1(
            connected=True,
            can_publish=True,
            external_identity=connection["external_identity"],
            api_version="202608",
            observed_at=datetime.now(timezone.utc),
        )

    async def publish(self, prepared, connection):
        self.calls += 1
        return _receipt()

    async def reconcile(self, publication, connection):
        return _receipt(publication.external_post_id or "urn:li:share:reconciled")


class StaticBuilder:
    async def build(self, *, tenant_id, publication):
        return PreparedPublication(
            commentary="Approved S10 text",
            image_bytes=None,
            image_sha256=None,
            image_content_type=None,
            approval_bundle_sha256=publication.bundle_sha256,
        )


def test_publication_operation_key_binds_tenant_identity_and_bundle():
    args = dict(
        tenant_id="tenant-a",
        approval_id="approval-a",
        bundle_sha256="a" * 64,
        provider="linkedin",
        external_identity="urn:li:person:1",
        destination="member_feed",
    )
    baseline = publication_operation_key(**args)
    assert baseline == publication_operation_key(**args)
    assert baseline != publication_operation_key(**{**args, "tenant_id": "tenant-b"})
    assert baseline != publication_operation_key(**{**args, "external_identity": "urn:li:person:2"})
    assert baseline != publication_operation_key(**{**args, "bundle_sha256": "b" * 64})


@pytest.mark.asyncio
async def test_mongo_publication_atomic_claim_and_tenant_isolation():
    client, db = await _mongo()
    try:
        repo = MongoPublicationRepository(db, _context("tenant-a"))
        other = MongoPublicationRepository(db, _context("tenant-b"))
        publication = _publication(tenant="tenant-a")
        await repo.create(publication)

        first, second = await asyncio.gather(
            repo.claim(publication.publication_id, attempt_id="attempt-a", now=datetime.now(timezone.utc)),
            repo.claim(publication.publication_id, attempt_id="attempt-b", now=datetime.now(timezone.utc)),
        )
        statuses = {first[0], second[0]}
        assert "CLAIMED" in statuses
        assert "PUBLISHING" in statuses
        assert await other.get(publication.publication_id) is None
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_s9_s10_duplicate_delivery_crosses_external_boundary_once():
    client, db = await _mongo()
    try:
        context = _context()
        publications = MongoPublicationRepository(db, context)
        schedules = MongoScheduleRepository(db, context)
        connections = MongoConnectionRepository(db, context)
        adapter = CountingAdapter()
        now = datetime.now(timezone.utc)
        await connections.upsert_linkedin_oauth(
            external_identity="urn:li:person:123",
            display_name="S10",
            picture_url=None,
            encrypted_access_token="opaque-test-token",
            scopes=["openid", "profile", "w_member_social"],
            expires_at=now + timedelta(hours=1),
            connected_at=now,
        )
        connection = await connections.get_linkedin()
        publication = _publication().model_copy(update={"connection_id": connection["connection_id"]})
        schedule = ScheduleV1(
            schedule_id="schedule-s10",
            tenant_id=context.tenant_id,
            approval_id=publication.approval_id,
            connection_id=connection["connection_id"],
            provider="linkedin",
            destination=publication.destination,
            scheduled_for=now,
            timezone_context="America/Lima",
            state=ScheduleState.DISPATCHED,
            job_key=publication.idempotency_key,
            bundle_sha256=publication.bundle_sha256,
            created_at=now,
            dispatched_at=now,
        )
        await schedules.create(schedule)
        await publications.create(publication)

        jobs = MongoPublishJobOutboxRepository(db)
        transport = RecordingTransport()
        coordinator = JobCoordinator(repository=jobs, transport=transport, rediscovery_seconds=0)
        job = await coordinator.enqueue(
            tenant_id=context.tenant_id,
            kind="publish.linkedin.v1",
            idempotency_key=publication.idempotency_key,
            payload={
                "publication_id": publication.publication_id,
                "schedule_id": schedule.schedule_id,
                "approval_id": publication.approval_id,
                "bundle_sha256": publication.bundle_sha256,
                "provider": "linkedin",
                "destination": publication.destination,
            },
        )
        handler = PublishWorkerHandler(
            publications=publications,
            schedules=schedules,
            connections=connections,
            builder=StaticBuilder(),
            adapter=adapter,
        )
        messages = [
            TransportMessage("1-0", job.tenant_id, job.job_id, job.kind, job.payload_sha256),
            TransportMessage("2-0", job.tenant_id, job.job_id, job.kind, job.payload_sha256),
        ]
        first = await coordinator.process_message(message=messages[0], worker_id="w1", handler=handler)
        second = await coordinator.process_message(message=messages[1], worker_id="w2", handler=handler)
        current = await publications.get(publication.publication_id)
        final_schedule = await schedules.get(schedule.schedule_id)

        assert first.status == "SUCCEEDED"
        assert second.status == "ALREADY_SUCCEEDED"
        assert adapter.calls == 1
        assert current is not None and current.state is PublicationState.PUBLISHED
        assert current.receipt_digest
        assert final_schedule is not None and final_schedule.state is ScheduleState.COMPLETED
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_recovered_publishing_never_blindly_calls_provider():
    client, db = await _mongo()
    try:
        context = _context()
        publications = MongoPublicationRepository(db, context)
        schedules = MongoScheduleRepository(db, context)
        connections = MongoConnectionRepository(db, context)
        now = datetime.now(timezone.utc)
        await connections.upsert_linkedin_oauth(
            external_identity="urn:li:person:123",
            display_name="S10",
            picture_url=None,
            encrypted_access_token="opaque",
            scopes=["openid", "profile", "w_member_social"],
            expires_at=now + timedelta(hours=1),
            connected_at=now,
        )
        connection = await connections.get_linkedin()
        publication = _publication().model_copy(update={"connection_id": connection["connection_id"]})
        await publications.create(publication)
        status, claimed = await publications.claim(
            publication.publication_id, attempt_id="crashed-attempt", now=now
        )
        assert status == "CLAIMED" and claimed is not None
        adapter = CountingAdapter()
        handler = PublishWorkerHandler(
            publications=publications,
            schedules=schedules,
            connections=connections,
            builder=StaticBuilder(),
            adapter=adapter,
        )
        await handler(
            SimpleNamespace(
                kind="publish.linkedin.v1",
                tenant_id=context.tenant_id,
                payload={
                    "publication_id": publication.publication_id,
                    "bundle_sha256": publication.bundle_sha256,
                },
            )
        )
        current = await publications.get(publication.publication_id)
        assert adapter.calls == 0
        assert current is not None and current.state is PublicationState.RECONCILIATION_REQUIRED
        assert "automatic replay blocked" in (current.reconciliation_reason or "")
    finally:
        await client.drop_database(db.name)
        client.close()


class FakeResponse:
    def __init__(self, status_code: int, *, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected provider request")
        return self.responses.pop(0)


def _linkedin_adapter(responses):
    settings = LinkedInOAuthSettings(
        client_id="client",
        client_secret="secret",
        redirect_uri="http://localhost:8000/api/integrations/linkedin/callback",
        token_key="s10-test-token-key-that-is-long-enough-123456",
        api_version="202608",
        frontend_url="http://localhost:3000",
    )
    client = ScriptedClient(responses)
    adapter = LinkedInPlatformAdapter(settings=settings, client=client)
    connection = {
        "status": "CONNECTED",
        "external_identity": "urn:li:person:123",
        "encrypted_access_token": LinkedInTokenCipher(settings.token_key).encrypt("token"),
        "scopes": ["openid", "profile", "w_member_social"],
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return adapter, client, connection


@pytest.mark.asyncio
async def test_linkedin_text_and_single_image_contracts_and_version_header():
    adapter, client, connection = _linkedin_adapter(
        [FakeResponse(201, headers={"x-restli-id": "urn:li:share:text"})]
    )
    receipt = await adapter.publish(
        PreparedPublication("text", None, None, None, "a" * 64), connection
    )
    assert receipt.external_post_id == "urn:li:share:text"
    post = client.requests[-1]
    assert post[1].endswith("/rest/posts")
    assert post[2]["headers"]["Linkedin-Version"] == "202608"
    assert post[2]["headers"]["X-Restli-Protocol-Version"] == "2.0.0"

    image = b"s10-image-bytes"
    adapter, client, connection = _linkedin_adapter(
        [
            FakeResponse(200, payload={"value": {"uploadUrl": "https://upload.test", "image": "urn:li:image:1"}}),
            FakeResponse(201),
            FakeResponse(201, headers={"x-restli-id": "urn:li:share:image"}),
        ]
    )
    image_receipt = await adapter.publish(
        PreparedPublication(
            "image",
            image,
            hashlib.sha256(image).hexdigest(),
            "image/png",
            "b" * 64,
        ),
        connection,
    )
    assert image_receipt.external_asset_ids == ("urn:li:image:1",)
    assert [request[0] for request in client.requests] == ["POST", "PUT", "POST"]


@pytest.mark.asyncio
async def test_linkedin_429_is_safe_but_5xx_is_uncertain():
    adapter, _, connection = _linkedin_adapter([FakeResponse(429)])
    with pytest.raises(PlatformSafeFailure, match="429"):
        await adapter.publish(PreparedPublication("text", None, None, None, "a" * 64), connection)

    adapter, _, connection = _linkedin_adapter([FakeResponse(503)])
    with pytest.raises(PlatformUncertainFailure, match="uncertain"):
        await adapter.publish(PreparedPublication("text", None, None, None, "a" * 64), connection)


@pytest.mark.asyncio
async def test_builder_rehashes_approved_asset_bytes_immediately_before_upload():
    content = ContentSpecV1(
        content_spec_id="spec-s10",
        plan_id="plan-s10",
        language="en",
        hook="Approved hook",
        body="Approved body",
        format="text",
        format_spec=TextFormatSpecV1(),
        claims_used=(),
    )
    content_digest = production_sha256(content)
    expected_bytes = b"approved-bytes"
    expected_sha = hashlib.sha256(expected_bytes).hexdigest()
    base = {
        "schema_version": 2,
        "approval_id": "approval-s10",
        "tenant_id": "tenant-s10",
        "content_id": "content-s10",
        "revision_id": "revision-s10",
        "profile_snapshot_digest": "1" * 64,
        "plan_digest": "2" * 64,
        "research_digest": "3" * 64,
        "content_digest": content_digest,
        "visual_spec_digest": "4" * 64,
        "assets": (ApprovalAssetV2(asset_id="asset-s10", sha256=expected_sha),),
        "qa_digest": "5" * 64,
        "policy_version": "s10-policy",
        "approved_by": "operator",
        "approved_at": datetime.now(timezone.utc),
    }
    approval = ApprovalBundleV2(**base, bundle_sha256=canonical_approval_sha256(base))
    publication = _publication().model_copy(update={"bundle_sha256": approval.bundle_sha256})
    revision = SimpleNamespace(
        tenant_id="tenant-s10",
        content_id="content-s10",
        revision_id="revision-s10",
        content_spec_digest=content_digest,
        visual_spec_digest="4" * 64,
        asset_refs=("asset-s10",),
        content_spec_ref="spec-s10",
    )
    asset = SimpleNamespace(
        tenant_id="tenant-s10",
        revision_id="revision-s10",
        asset_id="asset-s10",
        page_index=0,
        sha256=expected_sha,
        storage_key="renders/test/page-00.png",
        byte_size=len(expected_bytes),
        content_type=RenderContentType.PNG,
    )

    class Approvals:
        async def get_bundle(self, tenant_id, approval_id): return approval
    class Production:
        async def get_revision(self, tenant_id, revision_id): return revision
        async def get_artifact(self, tenant_id, ref): return {"digest": content_digest, "payload": content.model_dump(mode="json")}
    class Rendering:
        async def get_asset(self, asset_id): return asset
    class CorruptStore:
        async def get(self, key): return b"corrupted-after-approval"

    builder = PreparedPublicationBuilder(
        approvals=Approvals(), production=Production(), rendering=Rendering(), asset_store=CorruptStore()
    )
    with pytest.raises(PlatformSafeFailure, match="bytes/hash changed"):
        await builder.build(tenant_id="tenant-s10", publication=publication)


@pytest.mark.asyncio
async def test_legacy_connection_bridge_is_bootstrap_only_and_safe_status_hides_token(monkeypatch):
    client, db = await _mongo()
    try:
        monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "s10-bridge-test")
        tenant_id = bootstrap_tenant_id()
        now = datetime.now(timezone.utc)
        legacy = {
            "_id": "primary",
            "provider": "linkedin",
            "status": "CONNECTED",
            "author_urn": "urn:li:person:legacy",
            "display_name": "Legacy member",
            "encrypted_access_token": "encrypted-secret-must-not-leak",
            "scopes": ["openid", "profile", "w_member_social"],
            "connected_at": now,
            "expires_at": now + timedelta(hours=1),
        }
        await db["linkedin_connections"].insert_one(legacy)
        report = await migrate_legacy_linkedin_connection(db)
        assert report.found_legacy and report.migrated
        repo = MongoConnectionRepository(
            db, TenantContext(tenant_id=tenant_id, actor_id="test", actor_type="service")
        )
        raw = await repo.get_linkedin()
        assert raw["encrypted_access_token"] == "encrypted-secret-must-not-leak"
        safe = await repo.safe_status()
        assert "encrypted_access_token" not in safe
        assert "secret" not in repr(safe).lower()

        wrong = MongoConnectionRepository(db, _context("another-tenant"))
        with pytest.raises(ValueError, match="bootstrap"):
            await wrong.import_legacy_linkedin(legacy, allow_bootstrap=True)
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_s10_real_redis_publish_stream_pending_recovery():
    if os.getenv("S10_REDIS_INTEGRATION", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("real Redis is exercised by S10-CERT")
    client, db = await _mongo()
    suffix = uuid4().hex
    settings = RedisStreamsSettings(
        url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        stream=f"pa:publish:v1:test:{suffix}",
        group=f"pa-publish-test-{suffix}",
        dead_letter_stream=f"pa:publish:v1:dead:test:{suffix}",
    )
    transport = RedisStreamsTransport(settings)
    repo = MongoPublishJobOutboxRepository(db)
    coordinator = JobCoordinator(repository=repo, transport=transport, rediscovery_seconds=0, lease_seconds=1)
    try:
        job = await coordinator.enqueue(
            tenant_id="tenant-real-s10",
            kind="publish.linkedin.v1",
            idempotency_key="publish-real",
            payload={"publication_id": "pub-real", "bundle_sha256": "a" * 64},
        )
        assert await coordinator.dispatch_once(tenant_id="tenant-real-s10") == 1
        abandoned = await transport.read(consumer="consumer-a", block_ms=50)
        assert len(abandoned) == 1 and abandoned[0].job_id == job.job_id
        recovered = await transport.recover_pending(consumer="consumer-b", min_idle_ms=0, count=10)
        assert [item.job_id for item in recovered] == [job.job_id]
        calls = []
        async def handler(claimed): calls.append(claimed.job_id)
        outcome = await coordinator.process_message(message=recovered[0], worker_id="consumer-b", handler=handler)
        assert outcome.status == "SUCCEEDED"
        assert calls == [job.job_id]
    finally:
        try:
            await transport._command("DEL", settings.stream, settings.dead_letter_stream)
        except Exception:
            pass
        await transport.close()
        await client.drop_database(db.name)
        client.close()
