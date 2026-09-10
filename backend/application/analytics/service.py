from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from domain.analytics.models import (
    ANALYTICS_POLICY_VERSION,
    ANALYTICS_SOURCE_VERSION,
    MetricSnapshotV1,
    NormalizedMetric,
    SnapshotFreshnessV1,
    analytics_operation_key,
    canonical_sha256,
    deterministic_snapshot_id,
)
from domain.jobs.models import JobIntent
from domain.publishing.models import PublicationState
from infrastructure.linkedin.analytics import AnalyticsSafeFailure


class AnalyticsAuthorityError(RuntimeError):
    pass


class AnalyticsUnavailable(AnalyticsAuthorityError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_millis(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


COLLECTION_WINDOWS: tuple[tuple[str, timedelta], ...] = (
    ("t+1h", timedelta(hours=1)),
    ("t+24h", timedelta(hours=24)),
    ("t+72h", timedelta(hours=72)),
    ("t+7d", timedelta(days=7)),
)


@dataclass(frozen=True)
class EnqueueResult:
    publication_id: str
    collection_bucket: str
    operation_key: str


def _connection_generation(connection: dict) -> str:
    marker = connection.get("updated_at") or connection.get("connected_at")
    if isinstance(marker, datetime):
        marker = _utc_millis(marker).isoformat()
    return f"{connection.get('connection_id') or 'unknown'}|{marker or 'unknown'}"


def _expected_next_sync(publication, collection_bucket: str, captured_at: datetime) -> datetime | None:
    if publication.completed_at is None:
        return None
    completed_at = _utc_millis(publication.completed_at)
    for index, (bucket, _) in enumerate(COLLECTION_WINDOWS):
        if bucket == collection_bucket:
            if index + 1 >= len(COLLECTION_WINDOWS):
                return None
            return _utc_millis(completed_at + COLLECTION_WINDOWS[index + 1][1])
    for _, offset in COLLECTION_WINDOWS:
        candidate = _utc_millis(completed_at + offset)
        if candidate > captured_at:
            return candidate
    return None


class AnalyticsIntentPlanner:
    JOB_KIND = "analytics.linkedin.v1"

    def __init__(self, *, publications, connections, snapshots, adapter, jobs):
        self.publications = publications
        self.connections = connections
        self.snapshots = snapshots
        self.adapter = adapter
        self.jobs = jobs

    async def _capability(self):
        connection = await self.connections.get_linkedin()
        last_success = await self.snapshots.latest_captured_at()
        capability = await self.adapter.capabilities(connection, last_success_at=last_success)
        return connection, capability

    @staticmethod
    def _operation(publication, collection_bucket: str) -> str:
        return analytics_operation_key(
            tenant_id=publication.tenant_id,
            publication_id=publication.publication_id,
            provider=publication.provider,
            external_post_id=publication.external_post_id or "",
            collection_bucket=collection_bucket,
        )

    async def _enqueue_publication(
        self,
        *,
        publication,
        collection_bucket: str,
        connection: dict,
    ) -> EnqueueResult:
        if publication.state is not PublicationState.PUBLISHED:
            raise AnalyticsAuthorityError("Analytics requires a PUBLISHED Publication")
        if publication.provider_receipt is None or not publication.receipt_digest:
            raise AnalyticsAuthorityError("Analytics requires persisted Publication receipt authority")
        if not publication.external_post_id:
            raise AnalyticsAuthorityError("Published Publication has no provider post identity")
        operation_key = self._operation(publication, collection_bucket)
        if await self.snapshots.get_by_operation_key(operation_key) is not None:
            return EnqueueResult(publication.publication_id, collection_bucket, operation_key)

        connection_generation = _connection_generation(connection)
        payload = {
            "publication_id": publication.publication_id,
            "provider": publication.provider,
            "external_post_id": publication.external_post_id,
            "receipt_digest": publication.receipt_digest,
            "collection_bucket": collection_bucket,
            "operation_key": operation_key,
            "connection_generation": connection_generation,
        }
        job_generation_key = canonical_sha256(
            {"operation_key": operation_key, "connection_generation": connection_generation}
        )
        await self.jobs.enqueue(
            tenant_id=publication.tenant_id,
            kind=self.JOB_KIND,
            idempotency_key=job_generation_key,
            payload=payload,
        )
        return EnqueueResult(publication.publication_id, collection_bucket, operation_key)

    async def enqueue_due(
        self,
        *,
        tenant_id: str,
        now: datetime | None = None,
        limit: int = 250,
    ) -> int:
        now = _utc_millis(now or utc_now())
        connection, capability = await self._capability()
        if connection is None or not capability.analytics_available:
            return 0
        enqueued = 0
        for publication in await self.publications.list_published(limit=limit):
            if publication.tenant_id != tenant_id or publication.completed_at is None:
                continue
            completed_at = _utc_millis(publication.completed_at)
            for bucket, offset in COLLECTION_WINDOWS:
                if now < completed_at + offset:
                    continue
                operation_key = self._operation(publication, bucket)
                if await self.snapshots.get_by_operation_key(operation_key) is not None:
                    continue
                await self._enqueue_publication(
                    publication=publication,
                    collection_bucket=bucket,
                    connection=connection,
                )
                enqueued += 1
        return enqueued

    async def enqueue_manual(self, *, publication_id: str, now: datetime | None = None) -> EnqueueResult:
        now = _utc_millis(now or utc_now())
        publication = await self.publications.get_published(publication_id)
        if publication is None:
            raise AnalyticsAuthorityError("Published Publication not found")
        connection, capability = await self._capability()
        if connection is None or not capability.analytics_available:
            raise AnalyticsUnavailable(capability.reason or "LinkedIn analytics unavailable")
        bucket = now.strftime("manual-%Y%m%dT%H%MZ")
        return await self._enqueue_publication(
            publication=publication,
            collection_bucket=bucket,
            connection=connection,
        )


class AnalyticsWorkerHandler:
    JOB_KIND = AnalyticsIntentPlanner.JOB_KIND

    def __init__(self, *, publications, connections, snapshots, adapter):
        self.publications = publications
        self.connections = connections
        self.snapshots = snapshots
        self.adapter = adapter

    async def __call__(self, job: JobIntent) -> None:
        if job.kind != self.JOB_KIND:
            raise ValueError("analytics worker received unsupported job kind")
        publication_id = str(job.payload.get("publication_id") or "")
        collection_bucket = str(job.payload.get("collection_bucket") or "")
        operation_key = str(job.payload.get("operation_key") or "")
        if not publication_id or not collection_bucket or not operation_key:
            raise ValueError("analytics job payload is incomplete")
        if await self.snapshots.get_by_operation_key(operation_key) is not None:
            return

        publication = await self.publications.get_published(publication_id)
        if publication is None or publication.tenant_id != job.tenant_id:
            raise ValueError("analytics job has no tenant-scoped published Publication authority")
        if publication.state is not PublicationState.PUBLISHED:
            raise ValueError("analytics authority is not PUBLISHED")
        if publication.provider_receipt is None or publication.receipt_digest != job.payload.get("receipt_digest"):
            raise ValueError("analytics job receipt digest differs from Publication authority")
        if publication.external_post_id != job.payload.get("external_post_id"):
            raise ValueError("analytics job provider identity differs from Publication authority")
        expected_operation = analytics_operation_key(
            tenant_id=job.tenant_id,
            publication_id=publication.publication_id,
            provider=publication.provider,
            external_post_id=publication.external_post_id or "",
            collection_bucket=collection_bucket,
        )
        if operation_key != expected_operation:
            raise ValueError("analytics job operation identity mismatch")

        connection = await self.connections.get_linkedin()
        capability = await self.adapter.capabilities(
            connection,
            last_success_at=await self.snapshots.latest_captured_at(),
        )
        if connection is None or not capability.analytics_available:
            raise AnalyticsSafeFailure(capability.reason or "LinkedIn analytics unavailable")
        if job.payload.get("connection_generation") != _connection_generation(connection):
            raise AnalyticsSafeFailure("analytics job belongs to a superseded LinkedIn connection generation")

        observation = await self.adapter.collect(
            external_post_id=publication.external_post_id or "",
            connection=connection,
        )
        captured_at = _utc_millis(observation.observed_at)
        created_at = _utc_millis(utc_now())
        freshness = SnapshotFreshnessV1(
            observed_at=captured_at,
            expected_next_sync_at=_expected_next_sync(publication, collection_bucket, captured_at),
            policy_version=ANALYTICS_POLICY_VERSION,
        )
        payload = {
            "schema_version": 1,
            "metric_snapshot_id": deterministic_snapshot_id(operation_key),
            "operation_key": operation_key,
            "tenant_id": job.tenant_id,
            "publication_id": publication.publication_id,
            "provider": "linkedin",
            "external_post_id": publication.external_post_id or "",
            "captured_at": captured_at,
            "raw_available_metrics": dict(observation.raw_available_metrics),
            "normalized_metrics": dict(observation.normalized_metrics),
            "unavailable_metrics": tuple(observation.unavailable_metrics),
            "freshness": freshness.model_dump(mode="python"),
            "source_version": ANALYTICS_SOURCE_VERSION,
            "provider_api_version": observation.provider_api_version,
            "collection_bucket": collection_bucket,
            "raw_digest": observation.raw_digest,
            "created_at": created_at,
        }
        snapshot = MetricSnapshotV1(**payload, snapshot_digest=canonical_sha256(payload))
        await self.snapshots.append(snapshot)


class AnalyticsReadService:
    def __init__(self, *, publications, connections, snapshots, adapter):
        self.publications = publications
        self.connections = connections
        self.snapshots = snapshots
        self.adapter = adapter

    async def overview(self, *, now: datetime | None = None) -> dict:
        now = _utc_millis(now or utc_now())
        published = await self.publications.list_published(limit=5000)
        published_count = len(published)
        recent = await self.snapshots.list_recent(limit=5000)
        latest_by_publication: dict[str, MetricSnapshotV1] = {}
        buckets_by_publication: dict[str, set[str]] = {}
        for snapshot in recent:
            latest_by_publication.setdefault(snapshot.publication_id, snapshot)
            buckets_by_publication.setdefault(snapshot.publication_id, set()).add(snapshot.collection_bucket)

        metric_names = tuple(metric.value for metric in NormalizedMetric)
        totals = {name: 0 for name in metric_names}
        coverage = {name: 0 for name in metric_names}
        for snapshot in latest_by_publication.values():
            for name, value in snapshot.normalized_metrics.items():
                if name not in totals:
                    continue
                totals[name] += value
                coverage[name] += 1

        latest_success_at = await self.snapshots.latest_captured_at()
        connection = await self.connections.get_linkedin()
        capability = await self.adapter.capabilities(connection, last_success_at=latest_success_at)

        stale = False
        complete_count = 0
        for publication in published:
            completed_at = publication.completed_at
            if completed_at is None:
                continue
            completed_at = _utc_millis(completed_at)
            observed_buckets = buckets_by_publication.get(publication.publication_id, set())
            due = {bucket for bucket, offset in COLLECTION_WINDOWS if completed_at + offset <= now}
            if due - observed_buckets:
                stale = True
            if "t+7d" in observed_buckets:
                complete_count += 1

        if not capability.analytics_available:
            freshness_state = "DEGRADED"
        elif not recent:
            freshness_state = "NEVER_SYNCED"
        elif stale:
            freshness_state = "STALE"
        elif published_count > 0 and complete_count == published_count:
            freshness_state = "COMPLETE_V1"
        else:
            freshness_state = "FRESH"

        impression_name = NormalizedMetric.VIEWS_OR_IMPRESSIONS.value
        interaction_names = (
            NormalizedMetric.LIKES_OR_REACTIONS.value,
            NormalizedMetric.COMMENTS.value,
            NormalizedMetric.SHARES.value,
        )
        interaction_coverage = {name: coverage[name] for name in interaction_names}
        observed_interaction_values = [totals[name] for name in interaction_names if coverage[name] > 0]
        normalized_totals = {
            name: totals[name] if coverage[name] > 0 else None
            for name in metric_names
        }
        return {
            "published_content_count": published_count,
            "measured_publication_count": len(latest_by_publication),
            "normalized_totals": normalized_totals,
            "coverage": coverage,
            "impressions_or_views": normalized_totals[impression_name],
            "impressions_coverage_count": coverage[impression_name],
            "interactions": sum(observed_interaction_values) if observed_interaction_values else None,
            "interaction_coverage": interaction_coverage,
            "last_success_at": latest_success_at,
            "freshness_state": freshness_state,
            "analytics_policy_version": ANALYTICS_POLICY_VERSION,
            "capability": capability.model_dump(mode="json"),
            "latest_snapshots": [
                snapshot.model_dump(mode="json")
                for snapshot in latest_by_publication.values()
            ],
        }

    async def publication_snapshots(self, publication_id: str, *, limit: int = 100) -> list[MetricSnapshotV1]:
        publication = await self.publications.get_published(publication_id)
        if publication is None:
            raise AnalyticsAuthorityError("Published Publication not found")
        return await self.snapshots.list_for_publication(publication_id, limit=limit)
