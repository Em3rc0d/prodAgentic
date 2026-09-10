from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256 = r"^[0-9a-f]{64}$"
PERFORMANCE_POLICY_VERSION = "s12-performance-v1"
MATURE_LEARNING_BUCKETS = ("t+7d", "t+72h")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfidenceBand(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PerformanceDimension(str, Enum):
    ROLE = "role"
    CANONICAL_TOPIC = "canonical_topic"
    FORMAT = "format"
    HOOK_PATTERN = "hook_pattern"
    VISUAL_PATTERN = "visual_pattern"
    PLATFORM = "platform"


class PerformanceObservationV1(FrozenModel):
    schema_version: Literal[1] = 1
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    publication_id: str = Field(min_length=1, max_length=128)
    metric_snapshot_id: str = Field(min_length=1, max_length=128)
    snapshot_digest: str = Field(pattern=_SHA256)
    captured_at: datetime
    provider: Literal["linkedin"] = "linkedin"
    role: str = Field(min_length=1, max_length=80)
    canonical_topic: str = Field(min_length=1, max_length=240)
    format: str = Field(min_length=1, max_length=80)
    hook_pattern: str = Field(min_length=1, max_length=120)
    visual_pattern: str | None = Field(default=None, max_length=120)
    impressions: int = Field(gt=0)
    reactions: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)

    @field_validator("captured_at", mode="before")
    @classmethod
    def normalize_captured_at(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value


class PerformanceEvidenceSetV1(FrozenModel):
    schema_version: Literal[1] = 1
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    candidate_snapshot_count: int = Field(ge=0)
    excluded_incomplete_count: int = Field(ge=0)
    excluded_unattributed_count: int = Field(ge=0)
    observations: tuple[PerformanceObservationV1, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self):
        for observation in self.observations:
            if observation.tenant_id != self.tenant_id or observation.profile_id != self.profile_id:
                raise ValueError("Performance evidence observation scope mismatch")
        if len({item.publication_id for item in self.observations}) != len(self.observations):
            raise ValueError("Performance evidence must contain at most one observation per publication")
        return self


class PerformanceSignalV1(FrozenModel):
    schema_version: Literal[1] = 1
    signal_id: str = Field(min_length=1, max_length=128)
    dimension: PerformanceDimension
    key: str = Field(min_length=1, max_length=240)
    sample_size: int = Field(ge=1)
    mean_observation_score: float = Field(ge=0, le=1)
    baseline_score: float = Field(ge=0, le=1)
    lift: float = Field(ge=-1, le=1)
    confidence: ConfidenceBand
    planner_weight: float = Field(ge=0, le=1)
    note: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_confidence_weight(self):
        expected = {
            ConfidenceBand.INSUFFICIENT: 0.0,
            ConfidenceBand.LOW: 0.0,
            ConfidenceBand.MEDIUM: 0.5,
            ConfidenceBand.HIGH: 1.0,
        }[self.confidence]
        if self.planner_weight != expected:
            raise ValueError("planner_weight must follow the frozen S12 confidence policy")
        return self


class PerformanceSummaryV1(FrozenModel):
    schema_version: Literal[1] = 1
    summary_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    policy_version: Literal["s12-performance-v1"] = PERFORMANCE_POLICY_VERSION
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_size: int = Field(ge=0)
    eligible_publication_ids: tuple[str, ...] = ()
    input_snapshot_ids: tuple[str, ...] = ()
    input_digest: str = Field(pattern=_SHA256)
    baseline_score: float | None = Field(default=None, ge=0, le=1)
    signals: tuple[PerformanceSignalV1, ...] = ()
    insufficient_dimensions: tuple[PerformanceDimension, ...] = ()
    latest_snapshot_at: datetime | None = None
    limitations: tuple[str, ...] = ()
    summary_digest: str = Field(pattern=_SHA256)
    created_at: datetime

    @field_validator("window_start", "window_end", "latest_snapshot_at", "created_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value

    @model_validator(mode="after")
    def validate_summary(self):
        if self.sample_size != len(self.eligible_publication_ids):
            raise ValueError("sample_size must equal eligible publication count")
        if self.sample_size != len(self.input_snapshot_ids):
            raise ValueError("sample_size must equal input snapshot count")
        if len(set(self.eligible_publication_ids)) != len(self.eligible_publication_ids):
            raise ValueError("eligible_publication_ids must be unique")
        if len(set(self.input_snapshot_ids)) != len(self.input_snapshot_ids):
            raise ValueError("input_snapshot_ids must be unique")
        if self.sample_size == 0:
            if self.baseline_score is not None or self.latest_snapshot_at is not None:
                raise ValueError("empty summary cannot report baseline or latest snapshot")
            if self.window_start is not None or self.window_end is not None:
                raise ValueError("empty summary cannot report an evidence window")
        else:
            if self.baseline_score is None or self.latest_snapshot_at is None:
                raise ValueError("non-empty summary requires baseline and latest snapshot")
            if self.window_start is None or self.window_end is None or self.window_end < self.window_start:
                raise ValueError("non-empty summary requires an ordered evidence window")
        if len({item.signal_id for item in self.signals}) != len(self.signals):
            raise ValueError("PerformanceSummary signal IDs must be unique")
        expected = canonical_sha256(self, exclude={"summary_digest", "created_at"})
        if expected != self.summary_digest:
            raise ValueError("PerformanceSummaryV1 summary_digest mismatch")
        return self


class PlannerPerformanceScoreV1(FrozenModel):
    schema_version: Literal[1] = 1
    score: float = Field(ge=-1, le=1)
    matched_signal_ids: tuple[str, ...] = ()
    note: str = Field(min_length=1, max_length=500)


def confidence_for_sample(sample_size: int) -> ConfidenceBand:
    if sample_size < 3:
        return ConfidenceBand.INSUFFICIENT
    if sample_size < 5:
        return ConfidenceBand.LOW
    if sample_size < 10:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.HIGH


def planner_weight_for_confidence(confidence: ConfidenceBand) -> float:
    return {
        ConfidenceBand.INSUFFICIENT: 0.0,
        ConfidenceBand.LOW: 0.0,
        ConfidenceBand.MEDIUM: 0.5,
        ConfidenceBand.HIGH: 1.0,
    }[confidence]


def deterministic_summary_id(*, tenant_id: str, profile_id: str, input_digest: str) -> str:
    material = f"{PERFORMANCE_POLICY_VERSION}|{tenant_id}|{profile_id}|{input_digest}"
    return f"perf_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"


def deterministic_signal_id(*, profile_id: str, input_digest: str, dimension: str, key: str) -> str:
    material = f"{PERFORMANCE_POLICY_VERSION}|{profile_id}|{input_digest}|{dimension}|{key}"
    return f"sig_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"


def _mongo_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _json_default(item):
    if isinstance(item, datetime):
        value = _mongo_utc(item).isoformat(timespec="milliseconds")
        return value[:-6] + "Z" if value.endswith("+00:00") else value
    if isinstance(item, Enum):
        return item.value
    if isinstance(item, BaseModel):
        return item.model_dump(mode="python")
    return str(item)


def canonical_sha256(payload: BaseModel | dict | list | tuple, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="python", exclude=exclude or set())
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
