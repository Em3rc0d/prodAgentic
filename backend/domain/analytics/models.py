from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256 = r"^[0-9a-f]{64}$"
ANALYTICS_POLICY_VERSION = "linkedin-member-post-lifecycle-v1"
ANALYTICS_SOURCE_VERSION = "linkedin-member-post-v1"
LINKEDIN_MEMBER_METRICS_V1 = (
    "IMPRESSION",
    "MEMBERS_REACHED",
    "RESHARE",
    "REACTION",
    "COMMENT",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class NormalizedMetric(str, Enum):
    VIEWS_OR_IMPRESSIONS = "views_or_impressions"
    LIKES_OR_REACTIONS = "likes_or_reactions"
    COMMENTS = "comments"
    SHARES = "shares"


class AnalyticsCapabilityV1(FrozenModel):
    schema_version: Literal[1] = 1
    provider: Literal["linkedin"] = "linkedin"
    connected: bool
    analytics_available: bool
    analytics_scope_granted: bool
    supported_provider_metrics: tuple[str, ...] = ()
    external_identity: str | None = Field(default=None, max_length=256)
    api_version: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    observed_at: datetime
    last_success_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("observed_at", "last_success_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value


class MetricValueV1(FrozenModel):
    """One provider metric observation at the adapter boundary.

    `normalized_metric=None` is intentional for provider-specific evidence such
    as LinkedIn MEMBERS_REACHED, which is not equivalent to impressions/views.
    """

    schema_version: Literal[1] = 1
    normalized_metric: NormalizedMetric | None = None
    provider_metric: str = Field(min_length=1, max_length=120)
    availability: MetricAvailability
    value: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_availability(self):
        if self.availability is MetricAvailability.AVAILABLE and self.value is None:
            raise ValueError("AVAILABLE metric requires a numeric value")
        if self.availability is MetricAvailability.UNAVAILABLE and self.value is not None:
            raise ValueError("UNAVAILABLE metric must not carry a numeric value")
        return self


def _mongo_utc(value: datetime) -> datetime:
    """Normalize immutable analytics evidence to BSON millisecond precision."""

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


class SnapshotFreshnessV1(FrozenModel):
    observed_at: datetime
    expected_next_sync_at: datetime | None = None
    policy_version: str = Field(default=ANALYTICS_POLICY_VERSION, min_length=1, max_length=120)

    @field_validator("observed_at", "expected_next_sync_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value


class MetricSnapshotV1(FrozenModel):
    """Tenant-scoped append-only provider measurement authority."""

    schema_version: Literal[1] = 1
    metric_snapshot_id: str = Field(min_length=1, max_length=128)
    operation_key: str = Field(pattern=_SHA256)
    tenant_id: str = Field(min_length=1, max_length=128)
    publication_id: str = Field(min_length=1, max_length=128)
    provider: Literal["linkedin"] = "linkedin"
    external_post_id: str = Field(min_length=1, max_length=512)
    captured_at: datetime
    raw_available_metrics: dict[str, int]
    normalized_metrics: dict[str, int]
    unavailable_metrics: tuple[str, ...] = ()
    freshness: SnapshotFreshnessV1
    source_version: str = Field(default=ANALYTICS_SOURCE_VERSION, min_length=1, max_length=120)
    provider_api_version: str = Field(pattern=r"^[0-9]{6}$")
    collection_bucket: str = Field(min_length=1, max_length=64)
    raw_digest: str = Field(pattern=_SHA256)
    snapshot_digest: str = Field(pattern=_SHA256)
    created_at: datetime

    @field_validator("captured_at", "created_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.freshness.observed_at != self.captured_at:
            raise ValueError("freshness.observed_at must equal captured_at")
        if not self.raw_available_metrics:
            raise ValueError("MetricSnapshotV1 requires at least one observed provider metric")
        for key, value in self.raw_available_metrics.items():
            if not key or isinstance(value, bool) or value < 0:
                raise ValueError("raw_available_metrics requires non-negative integer observations")
        allowed_normalized = {metric.value for metric in NormalizedMetric}
        for key, value in self.normalized_metrics.items():
            if key not in allowed_normalized or isinstance(value, bool) or value < 0:
                raise ValueError("normalized_metrics contains unsupported or negative evidence")
        if len(self.unavailable_metrics) != len(set(self.unavailable_metrics)):
            raise ValueError("unavailable_metrics must not contain duplicates")
        if set(self.unavailable_metrics) & set(self.raw_available_metrics):
            raise ValueError("a provider metric cannot be both available and unavailable")

        normalized_sources = {
            NormalizedMetric.VIEWS_OR_IMPRESSIONS.value: "IMPRESSION",
            NormalizedMetric.LIKES_OR_REACTIONS.value: "REACTION",
            NormalizedMetric.COMMENTS.value: "COMMENT",
            NormalizedMetric.SHARES.value: "RESHARE",
        }
        for normalized_name in self.normalized_metrics:
            if normalized_sources[normalized_name] not in self.raw_available_metrics:
                raise ValueError("normalized metric requires matching provider evidence")

        if canonical_sha256(self.raw_available_metrics) != self.raw_digest:
            raise ValueError("MetricSnapshotV1 raw_digest mismatch")
        if canonical_sha256(self, exclude={"snapshot_digest"}) != self.snapshot_digest:
            raise ValueError("MetricSnapshotV1 snapshot_digest mismatch")
        return self


def _json_default(item):
    if isinstance(item, datetime):
        value = _mongo_utc(item).isoformat(timespec="milliseconds")
        return value[:-6] + "Z" if value.endswith("+00:00") else value
    if isinstance(item, Enum):
        return item.value
    return str(item)


def _canonical(value) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def canonical_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(exclude=exclude or set(), mode="python")
    return hashlib.sha256(_canonical(payload)).hexdigest()


def analytics_operation_key(
    *,
    tenant_id: str,
    publication_id: str,
    provider: str,
    external_post_id: str,
    collection_bucket: str,
    operation_version: str = "analytics-v1",
) -> str:
    material = {
        "operation_version": operation_version,
        "tenant_id": tenant_id,
        "publication_id": publication_id,
        "provider": provider,
        "external_post_id": external_post_id,
        "collection_bucket": collection_bucket,
    }
    return hashlib.sha256(_canonical(material)).hexdigest()


def deterministic_snapshot_id(operation_key: str) -> str:
    return f"metric_{operation_key[:40]}"
