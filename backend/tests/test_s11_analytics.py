from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from core.linkedin_oauth import LinkedInOAuthSettings, LinkedInTokenCipher
from domain.analytics.models import (
    ANALYTICS_SOURCE_VERSION,
    MetricAvailability,
    MetricSnapshotV1,
    MetricValueV1,
    NormalizedMetric,
    SnapshotFreshnessV1,
    analytics_operation_key,
    canonical_sha256,
    deterministic_snapshot_id,
)
from domain.tenants.models import TenantContext
from infrastructure.linkedin.analytics import (
    AnalyticsRetryableFailure,
    AnalyticsSafeFailure,
    LinkedInAnalyticsAdapter,
)
from infrastructure.mongo.analytics import MongoMetricSnapshotRepository, MetricSnapshotConflict


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_s11_{uuid4().hex}"]
    return client, db


def _context(tenant: str = "tenant-s11") -> TenantContext:
    return TenantContext(tenant_id=tenant, actor_id="s11-test", actor_type="worker")


def _ms(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _settings() -> LinkedInOAuthSettings:
    return LinkedInOAuthSettings(
        client_id="client",
        client_secret="secret",
        redirect_uri="http://localhost:8000/api/integrations/linkedin/callback",
        token_key="s11-certification-token-key-32-characters-minimum",
        api_version="202608",
        frontend_url="http://localhost:3000",
    )


def _connection(*, analytics_scope: bool = True) -> dict:
    settings = _settings()
    scopes = ["openid", "profile", "w_member_social"]
    if analytics_scope:
        scopes.append("r_member_postAnalytics")
    return {
        "connection_id": "conn-s11",
        "provider": "linkedin",
        "status": "CONNECTED",
        "external_identity": "urn:li:person:123",
        "encrypted_access_token": LinkedInTokenCipher(settings.token_key).encrypt("access-token"),
        "scopes": scopes,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }


def _snapshot(
    *,
    tenant: str = "tenant-s11",
    publication_id: str = "pub-s11",
    bucket: str = "t+1h",
    value: int = 42,
    captured_at: datetime | None = None,
) -> MetricSnapshotV1:
    operation_key = analytics_operation_key(
        tenant_id=tenant,
        publication_id=publication_id,
        provider="linkedin",
        external_post_id="urn:li:share:123",
        collection_bucket=bucket,
    )
    now = _ms(captured_at or datetime.now(timezone.utc))
    raw_available = {"IMPRESSION": value}
    freshness = SnapshotFreshnessV1(
        observed_at=now,
        expected_next_sync_at=now + timedelta(hours=23),
    )
    payload = {
        "schema_version": 1,
        "metric_snapshot_id": deterministic_snapshot_id(operation_key),
        "operation_key": operation_key,
        "tenant_id": tenant,
        "publication_id": publication_id,
        "provider": "linkedin",
        "external_post_id": "urn:li:share:123",
        "captured_at": now,
        "raw_available_metrics": raw_available,
        "normalized_metrics": {NormalizedMetric.VIEWS_OR_IMPRESSIONS.value: value},
        "unavailable_metrics": ("MEMBERS_REACHED", "POST_SAVE"),
        "freshness": freshness.model_dump(mode="python"),
        "source_version": ANALYTICS_SOURCE_VERSION,
        "provider_api_version": "202608",
        "collection_bucket": bucket,
        "raw_digest": canonical_sha256(raw_available),
        "created_at": now,
    }
    return MetricSnapshotV1(**payload, snapshot_digest=canonical_sha256(payload))


def test_metric_value_never_coerces_unavailable_to_zero():
    with pytest.raises(ValueError):
        MetricValueV1(
            normalized_metric=NormalizedMetric.COMMENTS,
            provider_metric="COMMENT",
            availability=MetricAvailability.UNAVAILABLE,
            value=0,
        )
    with pytest.raises(ValueError):
        MetricValueV1(
            normalized_metric=NormalizedMetric.COMMENTS,
            provider_metric="COMMENT",
            availability=MetricAvailability.AVAILABLE,
            value=None,
        )


def test_provider_specific_reach_can_remain_unmapped():
    reach = MetricValueV1(
        normalized_metric=None,
        provider_metric="MEMBERS_REACHED",
        availability=MetricAvailability.AVAILABLE,
        value=7,
    )
    assert reach.normalized_metric is None
    assert reach.value == 7


def test_explicit_zero_is_observed_evidence_not_unavailable():
    snapshot = _snapshot(value=0)
    assert snapshot.raw_available_metrics["IMPRESSION"] == 0
    assert snapshot.normalized_metrics["views_or_impressions"] == 0
    assert "IMPRESSION" not in snapshot.unavailable_metrics


def test_analytics_operation_key_binds_tenant_publication_post_and_bucket():
    args = dict(
        tenant_id="tenant-a",
        publication_id="pub-a",
        provider="linkedin",
        external_post_id="urn:li:share:1",
        collection_bucket="t+1h",
    )
    baseline = analytics_operation_key(**args)
    assert baseline == analytics_operation_key(**args)
    assert baseline != analytics_operation_key(**{**args, "tenant_id": "tenant-b"})
    assert baseline != analytics_operation_key(**{**args, "publication_id": "pub-b"})
    assert baseline != analytics_operation_key(**{**args, "external_post_id": "urn:li:share:2"})
    assert baseline != analytics_operation_key(**{**args, "collection_bucket": "t+24h"})


@pytest.mark.asyncio
async def test_mongo_metric_snapshots_are_tenant_scoped_append_only_and_idempotent():
    client, db = await _mongo()
    try:
        repo = MongoMetricSnapshotRepository(db, _context("tenant-a"))
        other = MongoMetricSnapshotRepository(db, _context("tenant-b"))
        snapshot = _snapshot(tenant="tenant-a")
        first = await repo.append(snapshot)
        replay = await repo.append(snapshot)
        assert first == replay
        assert await other.get(snapshot.metric_snapshot_id) is None
        history = await repo.list_for_publication(snapshot.publication_id)
        assert history == [snapshot]
        assert await repo.collection.count_documents({"tenant_id": "tenant-a"}) == 1
        conflicting = _snapshot(tenant="tenant-a", value=99, captured_at=snapshot.captured_at)
        with pytest.raises(MetricSnapshotConflict):
            await repo.append(conflicting)
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_snapshot_history_appends_later_bucket_and_preserves_digest_after_mongo_roundtrip():
    client, db = await _mongo()
    try:
        repo = MongoMetricSnapshotRepository(db, _context())
        earlier = _ms(datetime.now(timezone.utc) - timedelta(hours=23))
        later = _ms(datetime.now(timezone.utc))
        first = _snapshot(bucket="t+1h", captured_at=earlier, value=10)
        second = _snapshot(bucket="t+24h", captured_at=later, value=40)
        await repo.append(first)
        await repo.append(second)
        history = await repo.list_for_publication("pub-s11")
        assert [item.collection_bucket for item in history] == ["t+24h", "t+1h"]
        assert history[0].snapshot_digest == second.snapshot_digest
        assert canonical_sha256(history[0], exclude={"snapshot_digest"}) == history[0].snapshot_digest
        latest = await repo.latest_captured_at()
        assert latest == later
        assert await repo.collection.count_documents({"tenant_id": "tenant-s11"}) == 2
    finally:
        await client.drop_database(db.name)
        client.close()


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class RecordingAnalyticsClient:
    def __init__(self, *, status_code: int = 200):
        self.status_code = status_code
        self.calls: list[tuple[str, str, dict]] = []

    async def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        metric = url.split("queryType=", 1)[1].split("&", 1)[0]
        if self.status_code != 200:
            return FakeResponse(self.status_code, {})
        if metric == "MEMBERS_REACHED":
            return FakeResponse(200, {"elements": []})
        return FakeResponse(200, {"elements": [{"metricType": metric, "count": 7}]})


@pytest.mark.asyncio
async def test_linkedin_adapter_core_five_contract_headers_and_unavailable_metric():
    client = RecordingAnalyticsClient()
    adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=client)
    observation = await adapter.collect(
        external_post_id="urn:li:share:999",
        connection=_connection(),
    )
    assert len(client.calls) == 5
    assert observation.raw_available_metrics == {
        "IMPRESSION": 7,
        "RESHARE": 7,
        "REACTION": 7,
        "COMMENT": 7,
    }
    assert observation.unavailable_metrics == ("MEMBERS_REACHED",)
    assert "members_reached" not in observation.normalized_metrics
    for method, url, kwargs in client.calls:
        assert method == "GET"
        assert "/rest/memberCreatorPostAnalytics?q=entity" in url
        assert "aggregation=TOTAL" in url
        assert "(share:urn%3Ali%3Ashare%3A999)" in url
        assert kwargs["headers"]["Linkedin-Version"] == "202608"
        assert kwargs["headers"]["X-Restli-Protocol-Version"] == "2.0.0"
        assert kwargs["headers"]["Authorization"] == "Bearer access-token"


@pytest.mark.asyncio
async def test_analytics_scope_is_independent_and_provider_failures_are_classified():
    adapter = LinkedInAnalyticsAdapter(settings=_settings(), client=RecordingAnalyticsClient())
    capability = await adapter.capabilities(_connection(analytics_scope=False))
    assert capability.connected is True
    assert capability.analytics_available is False
    assert capability.analytics_scope_granted is False
    assert "permission" in (capability.reason or "").lower()

    for status in (429, 503, 408):
        failing = LinkedInAnalyticsAdapter(settings=_settings(), client=RecordingAnalyticsClient(status_code=status))
        with pytest.raises(AnalyticsRetryableFailure):
            await failing.collect(external_post_id="urn:li:share:999", connection=_connection())

    unauthorized = LinkedInAnalyticsAdapter(settings=_settings(), client=RecordingAnalyticsClient(status_code=403))
    with pytest.raises(AnalyticsSafeFailure):
        await unauthorized.collect(external_post_id="urn:li:share:999", connection=_connection())
