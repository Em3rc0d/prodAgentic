from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from application.analytics.service import AnalyticsWorkerHandler, _connection_generation
from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.analytics.models import AnalyticsCapabilityV1, NormalizedMetric
from domain.jobs.models import JobIntent, payload_digest
from domain.publishing.models import PublicationState
from domain.tenants.models import TenantContext
from infrastructure.linkedin.analytics import (
    AnalyticsObservation,
    AnalyticsRetryableFailure,
    AnalyticsSafeFailure,
    LinkedInAnalyticsAdapter,
)
from infrastructure.linkedin.oauth import S10LinkedInOAuthService


def _settings() -> LinkedInOAuthSettings:
    return LinkedInOAuthSettings(
        client_id="s11-client",
        client_secret="s11-client-secret",
        redirect_uri="http://localhost:8000/api/integrations/linkedin/callback",
        token_key="s11-token-key-1234567890-abcdefghijklmnopqrstuvwxyz",
        api_version="202608",
        frontend_url="http://localhost:3000",
    )


def _connection(*, include_scope: bool = True) -> dict:
    settings = _settings()
    scopes = ["openid", "profile", "w_member_social"]
    if include_scope:
        scopes.append("r_member_postAnalytics")
    now = datetime.now(timezone.utc)
    return {
        "tenant_id": "tenant-s11",
        "connection_id": "conn-s11",
        "provider": "linkedin",
        "status": "CONNECTED",
        "external_identity": "urn:li:person:s11",
        "encrypted_access_token": LinkedInTokenCipher(settings.token_key).encrypt("token-s11"),
        "scopes": scopes,
        "expires_at": now + timedelta(hours=2),
        "connected_at": now - timedelta(minutes=5),
        "updated_at": now - timedelta(minutes=5),
    }


def _response(metric: str, count: int | None) -> httpx.Response:
    elements = [] if count is None else [{"metricType": metric, "count": count}]
    return httpx.Response(200, json={"elements": elements})


@pytest.mark.asyncio
async def test_linkedin_adapter_contract_keeps_zero_and_reach_raw_only():
    seen: list[httpx.Request] = []
    counts = {
        "IMPRESSION": 0,
        "MEMBERS_REACHED": 91,
        "RESHARE": 2,
        "REACTION": 12,
        "COMMENT": None,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        query = parse_qs(request.url.query.decode())
        metric = query["queryType"][0]
        assert request.url.path == "/rest/memberCreatorPostAnalytics"
        assert query["q"] == ["entity"]
        assert query["aggregation"] == ["TOTAL"]
        assert "urn%3Ali%3Ashare%3A123" in request.url.query.decode()
        assert request.headers["Linkedin-Version"] == "202608"
        assert request.headers["X-Restli-Protocol-Version"] == "2.0.0"
        assert request.headers["Authorization"] == "Bearer token-s11"
        return _response(metric, counts[metric])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=client)
        observation = await adapter.collect(
            external_post_id="urn:li:share:123",
            connection=_connection(),
        )

    assert len(seen) == 5
    assert observation.raw_available_metrics["IMPRESSION"] == 0
    assert observation.normalized_metrics[NormalizedMetric.VIEWS_OR_IMPRESSIONS.value] == 0
    assert observation.raw_available_metrics["MEMBERS_REACHED"] == 91
    assert "members_reached" not in observation.normalized_metrics
    assert "COMMENT" in observation.unavailable_metrics
    assert "IMPRESSION" not in observation.unavailable_metrics


@pytest.mark.asyncio
async def test_missing_analytics_scope_is_capability_degradation_with_zero_http_calls():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=client)
        connection = _connection(include_scope=False)
        capability = await adapter.capabilities(connection)
        assert capability.connected is True
        assert capability.analytics_available is False
        assert capability.analytics_scope_granted is False
        assert "permission" in (capability.reason or "").lower()
        with pytest.raises(AnalyticsSafeFailure):
            await adapter.collect(external_post_id="urn:li:share:123", connection=connection)

    assert calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503, 408])
async def test_linkedin_read_transient_failures_are_retryable_without_snapshot_evidence(status: int):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "temporary"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=client)
        with pytest.raises(AnalyticsRetryableFailure):
            await adapter.collect(
                external_post_id="urn:li:share:123",
                connection=_connection(),
            )


@pytest.mark.asyncio
async def test_linkedin_malformed_evidence_fails_safe_without_fabricated_metric():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": [{"metricType": "WRONG", "count": 1}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=client)
        with pytest.raises(AnalyticsSafeFailure):
            await adapter.collect(
                external_post_id="urn:li:share:123",
                connection=_connection(),
            )


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_s11_provider_{uuid4().hex}"]
    return client, db


@pytest.mark.asyncio
async def test_oauth_analytics_upgrade_requests_extra_scope_without_changing_base_publish_scopes():
    client, db = await _mongo()
    try:
        context = TenantContext(tenant_id="tenant-s11", actor_id="s11-test", actor_type="worker")
        service = S10LinkedInOAuthService(db, context, settings=_settings())
        url = await service.create_authorization_url(
            "session-s11",
            extra_scopes=(LinkedInAnalyticsAdapter.REQUIRED_SCOPE,),
        )
        scopes = set(parse_qs(urlparse(url).query)["scope"][0].split())
        assert scopes == {"openid", "profile", "w_member_social", "r_member_postAnalytics"}
        assert "r_member_postAnalytics" not in set(_settings().scopes)
        state_doc = await db["linkedin_oauth_states_v2"].find_one({"tenant_id": "tenant-s11"})
        assert state_doc is not None
        assert set(state_doc["requested_scopes"]) == scopes
    finally:
        await client.drop_database(db.name)
        client.close()


class _Snapshots:
    def __init__(self):
        self.items = {}

    async def get_by_operation_key(self, operation_key: str):
        return self.items.get(operation_key)

    async def append(self, snapshot):
        self.items.setdefault(snapshot.operation_key, snapshot)
        return self.items[snapshot.operation_key]

    async def latest_captured_at(self):
        if not self.items:
            return None
        return max(item.captured_at for item in self.items.values())


class _Publications:
    def __init__(self, publication):
        self.publication = publication

    async def get_published(self, publication_id: str):
        return self.publication if publication_id == self.publication.publication_id else None


class _Connections:
    def __init__(self, connection: dict):
        self.connection = connection

    async def get_linkedin(self):
        return self.connection


class _Adapter:
    def __init__(self):
        self.calls = 0

    async def capabilities(self, connection, *, last_success_at=None):
        return AnalyticsCapabilityV1(
            connected=True,
            analytics_available=True,
            analytics_scope_granted=True,
            supported_provider_metrics=LinkedInAnalyticsAdapter.PROVIDER_METRICS,
            external_identity=connection["external_identity"],
            api_version="202608",
            observed_at=datetime.now(timezone.utc),
            last_success_at=last_success_at,
        )

    async def collect(self, *, external_post_id: str, connection: dict):
        self.calls += 1
        now = datetime.now(timezone.utc).replace(microsecond=123000)
        raw = {"IMPRESSION": 7, "MEMBERS_REACHED": 5}
        return AnalyticsObservation(
            provider_api_version="202608",
            observed_at=now,
            raw_available_metrics=raw,
            normalized_metrics={"views_or_impressions": 7},
            unavailable_metrics=("COMMENT", "REACTION", "RESHARE"),
            raw_digest=__import__("domain.analytics.models", fromlist=["canonical_sha256"]).canonical_sha256(raw),
        )


@pytest.mark.asyncio
async def test_duplicate_worker_delivery_crosses_provider_read_boundary_once_after_snapshot_success():
    connection = _connection()
    publication = SimpleNamespace(
        tenant_id="tenant-s11",
        publication_id="pub-s11",
        provider="linkedin",
        state=PublicationState.PUBLISHED,
        provider_receipt=object(),
        receipt_digest="d" * 64,
        external_post_id="urn:li:share:123",
        completed_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    snapshots = _Snapshots()
    adapter = _Adapter()
    handler = AnalyticsWorkerHandler(
        publications=_Publications(publication),
        connections=_Connections(connection),
        snapshots=snapshots,
        adapter=adapter,
    )
    from domain.analytics.models import analytics_operation_key

    operation_key = analytics_operation_key(
        tenant_id="tenant-s11",
        publication_id="pub-s11",
        provider="linkedin",
        external_post_id="urn:li:share:123",
        collection_bucket="t+1h",
    )
    payload = {
        "publication_id": "pub-s11",
        "provider": "linkedin",
        "external_post_id": "urn:li:share:123",
        "receipt_digest": "d" * 64,
        "collection_bucket": "t+1h",
        "operation_key": operation_key,
        "connection_generation": _connection_generation(connection),
    }
    job = JobIntent(
        tenant_id="tenant-s11",
        job_id="job-s11",
        kind="analytics.linkedin.v1",
        payload=payload,
        payload_sha256=payload_digest(payload),
        created_at=datetime.now(timezone.utc),
    )

    await handler(job)
    await handler(job)

    assert adapter.calls == 1
    assert len(snapshots.items) == 1
    snapshot = snapshots.items[operation_key]
    assert snapshot.raw_available_metrics["MEMBERS_REACHED"] == 5
    assert "members_reached" not in snapshot.normalized_metrics
    assert snapshot.snapshot_digest
