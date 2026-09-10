from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from domain.analytics.models import MetricSnapshotV1
from domain.learning.models import (
    MATURE_LEARNING_BUCKETS,
    PerformanceEvidenceSetV1,
    PerformanceObservationV1,
    PerformanceSummaryV1,
)
from domain.tenants.models import TenantContext


class PerformanceSummaryConflict(RuntimeError):
    pass


def _aware(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {key: _aware(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_aware(item) for item in value]
    return value


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    payload = dict(document)
    payload.pop("_id", None)
    return _aware(payload)


class MongoPerformanceSummaryRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.collection = db["performance_summaries_v1"]
        self._indexes_ready = False

    async def ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("summary_id", ASCENDING)],
            unique=True,
            name="tenant_performance_summary_unique",
        )
        await self.collection.create_index(
            [
                ("tenant_id", ASCENDING),
                ("profile_id", ASCENDING),
                ("input_digest", ASCENDING),
                ("policy_version", ASCENDING),
            ],
            unique=True,
            name="tenant_profile_performance_input_unique",
        )
        await self.collection.create_index(
            [("tenant_id", ASCENDING), ("profile_id", ASCENDING), ("created_at", DESCENDING)],
            name="tenant_profile_performance_latest",
        )
        self._indexes_ready = True

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    @staticmethod
    def _model(document: dict | None) -> PerformanceSummaryV1 | None:
        clean = _clean(document)
        return PerformanceSummaryV1.model_validate(clean) if clean else None

    async def append(self, summary: PerformanceSummaryV1) -> PerformanceSummaryV1:
        await self.ensure_indexes()
        if summary.tenant_id != self.context.tenant_id:
            raise ValueError("PerformanceSummary tenant does not match repository context")
        try:
            await self.collection.insert_one(summary.model_dump(mode="python"))
            return summary
        except DuplicateKeyError:
            existing = await self.get_by_input_digest(summary.profile_id, summary.input_digest)
            if existing is None:
                raw = await self.collection.find_one(self._scope({"summary_id": summary.summary_id}))
                existing = self._model(raw)
            if existing is not None and existing.summary_digest == summary.summary_digest:
                return existing
            raise PerformanceSummaryConflict(
                "PerformanceSummary deterministic identity already exists with different evidence"
            )

    async def get_by_input_digest(
        self,
        profile_id: str,
        input_digest: str,
    ) -> PerformanceSummaryV1 | None:
        await self.ensure_indexes()
        raw = await self.collection.find_one(
            self._scope({"profile_id": profile_id, "input_digest": input_digest})
        )
        return self._model(raw)

    async def latest_for_profile(self, profile_id: str) -> PerformanceSummaryV1 | None:
        await self.ensure_indexes()
        raw = await self.collection.find_one(
            self._scope({"profile_id": profile_id}),
            sort=[("created_at", DESCENDING)],
        )
        return self._model(raw)


class MongoPerformanceEvidenceRepository:
    """Tenant-scoped attribution from S11 snapshots back to immutable content dimensions."""

    def __init__(self, db: Any, context: TenantContext):
        self.db = db
        self.context = context
        self.profiles = db["profiles"]
        self.items = db["content_items"]
        self.approvals = db["approval_bundles"]
        self.publications = db["publications_v2"]
        self.snapshots = db["metric_snapshots_v1"]

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    async def list_for_profile(self, profile_id: str) -> PerformanceEvidenceSetV1:
        profile = await self.profiles.find_one(self._scope({"profile_id": profile_id}), {"profile_id": 1})
        if profile is None:
            raise LookupError("Profile not found")

        item_cursor = self.items.find(
            self._scope({"profile_id": profile_id}),
            {
                "content_id": 1,
                "role": 1,
                "canonical_topic": 1,
                "format": 1,
                "hook_pattern": 1,
                "visual_pattern": 1,
            },
        )
        items = [document async for document in item_cursor]
        item_by_id = {str(item.get("content_id")): item for item in items if item.get("content_id")}
        if not item_by_id:
            return PerformanceEvidenceSetV1(
                tenant_id=self.context.tenant_id,
                profile_id=profile_id,
                candidate_snapshot_count=0,
                excluded_incomplete_count=0,
                excluded_unattributed_count=0,
                observations=(),
            )

        approval_cursor = self.approvals.find(
            self._scope({"content_id": {"$in": list(item_by_id)}}),
            {"approval_id": 1, "content_id": 1},
        )
        approvals = [document async for document in approval_cursor]
        content_by_approval = {
            str(document.get("approval_id")): str(document.get("content_id"))
            for document in approvals
            if document.get("approval_id") and document.get("content_id")
        }
        if not content_by_approval:
            return PerformanceEvidenceSetV1(
                tenant_id=self.context.tenant_id,
                profile_id=profile_id,
                candidate_snapshot_count=0,
                excluded_incomplete_count=0,
                excluded_unattributed_count=0,
                observations=(),
            )

        publication_cursor = self.publications.find(
            self._scope(
                {
                    "approval_id": {"$in": list(content_by_approval)},
                    "state": "PUBLISHED",
                }
            ),
            {"publication_id": 1, "approval_id": 1, "provider": 1},
        )
        publications = [document async for document in publication_cursor]
        publication_meta = {
            str(document.get("publication_id")): {
                "approval_id": str(document.get("approval_id")),
                "provider": str(document.get("provider") or ""),
            }
            for document in publications
            if document.get("publication_id") and document.get("approval_id")
        }
        if not publication_meta:
            return PerformanceEvidenceSetV1(
                tenant_id=self.context.tenant_id,
                profile_id=profile_id,
                candidate_snapshot_count=0,
                excluded_incomplete_count=0,
                excluded_unattributed_count=0,
                observations=(),
            )

        snapshot_cursor = self.snapshots.find(
            self._scope(
                {
                    "publication_id": {"$in": list(publication_meta)},
                    "collection_bucket": {"$in": list(MATURE_LEARNING_BUCKETS)},
                }
            )
        )
        raw_snapshots = [document async for document in snapshot_cursor]
        priority = {bucket: index for index, bucket in enumerate(MATURE_LEARNING_BUCKETS)}
        chosen: dict[str, MetricSnapshotV1] = {}
        invalid_snapshot_count = 0
        for raw in raw_snapshots:
            try:
                snapshot = MetricSnapshotV1.model_validate(_clean(raw))
            except Exception:
                invalid_snapshot_count += 1
                continue
            current = chosen.get(snapshot.publication_id)
            if current is None:
                chosen[snapshot.publication_id] = snapshot
                continue
            candidate_rank = priority.get(snapshot.collection_bucket, len(priority))
            current_rank = priority.get(current.collection_bucket, len(priority))
            if candidate_rank < current_rank or (
                candidate_rank == current_rank and snapshot.captured_at > current.captured_at
            ):
                chosen[snapshot.publication_id] = snapshot

        observations: list[PerformanceObservationV1] = []
        excluded_incomplete = invalid_snapshot_count
        excluded_unattributed = 0
        required_metrics = (
            "views_or_impressions",
            "likes_or_reactions",
            "comments",
            "shares",
        )
        for publication_id in sorted(chosen):
            snapshot = chosen[publication_id]
            meta = publication_meta.get(publication_id)
            if meta is None or meta.get("provider") != "linkedin":
                excluded_unattributed += 1
                continue
            content_id = content_by_approval.get(meta["approval_id"])
            item = item_by_id.get(content_id or "")
            if item is None:
                excluded_unattributed += 1
                continue
            metrics = snapshot.normalized_metrics
            if any(name not in metrics for name in required_metrics):
                excluded_incomplete += 1
                continue
            impressions = metrics["views_or_impressions"]
            if impressions <= 0:
                excluded_incomplete += 1
                continue
            observations.append(
                PerformanceObservationV1(
                    tenant_id=self.context.tenant_id,
                    profile_id=profile_id,
                    publication_id=publication_id,
                    metric_snapshot_id=snapshot.metric_snapshot_id,
                    snapshot_digest=snapshot.snapshot_digest,
                    captured_at=snapshot.captured_at,
                    provider="linkedin",
                    role=str(item.get("role") or ""),
                    canonical_topic=str(item.get("canonical_topic") or ""),
                    format=str(item.get("format") or ""),
                    hook_pattern=str(item.get("hook_pattern") or ""),
                    visual_pattern=(str(item.get("visual_pattern")) if item.get("visual_pattern") else None),
                    impressions=impressions,
                    reactions=metrics["likes_or_reactions"],
                    comments=metrics["comments"],
                    shares=metrics["shares"],
                )
            )

        return PerformanceEvidenceSetV1(
            tenant_id=self.context.tenant_id,
            profile_id=profile_id,
            candidate_snapshot_count=len(chosen),
            excluded_incomplete_count=excluded_incomplete,
            excluded_unattributed_count=excluded_unattributed,
            observations=tuple(observations),
        )
