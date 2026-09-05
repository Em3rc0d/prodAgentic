from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BatchState(str, Enum):
    PLANNED = "PLANNED"
    PARTIAL = "PARTIAL"


class ContentEditorialState(str, Enum):
    PLANNED = "PLANNED"


class LifecycleSource(str, Enum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"


class CooldownBand(str, Enum):
    HARD_COOLDOWN = "HARD_COOLDOWN"
    STRONG_COOLDOWN = "STRONG_COOLDOWN"
    ELIGIBLE = "ELIGIBLE"
    CURRENT_BATCH = "CURRENT_BATCH"


class NoveltyVerdict(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNING = "PASS_WITH_WARNING"
    REWRITE_ANGLE = "REWRITE_ANGLE"
    REPLACE_TOPIC = "REPLACE_TOPIC"
    BLOCKED = "BLOCKED"


class ClaimRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TargetWindow(FrozenModel):
    start_at: datetime
    end_at: datetime
    timezone: str = Field(min_length=1, max_length=80)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("target window datetimes require explicit timezone information")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return normalized

    @model_validator(mode="after")
    def ordered_window(self):
        if self.end_at <= self.start_at:
            raise ValueError("target window end_at must be after start_at")
        return self


class BatchRequestConstraints(StrictModel):
    campaign_goal: str | None = Field(default=None, max_length=240)
    include_topics: tuple[str, ...] = Field(default=(), max_length=8)
    avoid_topics: tuple[str, ...] = Field(default=(), max_length=12)
    channel_emphasis: str | None = Field(default=None, max_length=80)
    desired_format: Literal["text", "single_image", "carousel", "infographic"] | None = None

    @field_validator("campaign_goal", "channel_emphasis")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("include_topics", "avoid_topics")
    @classmethod
    def normalize_topics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(item.strip() for item in value if item.strip()))
        return normalized


class PlannerStrategySnapshot(FrozenModel):
    planner_policy_version: Literal["s2-planner-v1"] = "s2-planner-v1"
    taxonomy_version: Literal["s2-taxonomy-v1"] = "s2-taxonomy-v1"
    novelty_policy_version: Literal["s2-novelty-v1"] = "s2-novelty-v1"
    memory_window_days: int = Field(default=30, ge=7, le=180)
    memory_cutoff_at: datetime
    candidate_pool_size: int = Field(ge=1, le=24)
    performance_summary_version: None = None


class BatchSummaryCounts(FrozenModel):
    candidates_generated: int = Field(ge=0)
    candidates_blocked: int = Field(ge=0)
    candidates_rewrite: int = Field(ge=0)
    candidates_warning: int = Field(ge=0)
    selected: int = Field(ge=0)


class Batch(FrozenModel):
    batch_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    profile_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_window: TargetWindow
    requested_size: int = Field(ge=1, le=30)
    selected_size: int = Field(ge=0, le=30)
    request_constraints: BatchRequestConstraints
    strategy_snapshot: PlannerStrategySnapshot
    state: BatchState
    summary_counts: BatchSummaryCounts
    shortfall_reason: str | None = Field(default=None, max_length=400)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def selected_not_above_requested(self):
        if self.selected_size > self.requested_size:
            raise ValueError("selected_size cannot exceed requested_size")
        if self.selected_size < self.requested_size and self.state != BatchState.PARTIAL:
            raise ValueError("a short Batch must be explicitly PARTIAL")
        if self.selected_size == self.requested_size and self.state != BatchState.PLANNED:
            raise ValueError("a complete Batch must be PLANNED")
        return self


class IdeaCandidateV1(FrozenModel):
    schema_version: Literal[1] = 1
    candidate_id: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=240)
    subtopics: tuple[str, ...] = Field(default=(), max_length=12)
    angle: str = Field(min_length=1, max_length=240)
    hook_pattern: str = Field(min_length=1, max_length=120)
    target_effect: str = Field(min_length=1, max_length=160)
    tentative_format: Literal["text", "single_image", "carousel", "infographic"]
    rationale: str = Field(min_length=1, max_length=600)
    claim_risk: ClaimRisk = ClaimRisk.LOW


class NoveltyMatchV1(FrozenModel):
    memory_id: str | None = None
    content_id: str | None = None
    lifecycle_source: str
    cooldown_band: CooldownBand
    age_days: int | None = Field(default=None, ge=0)
    overlap_categories: tuple[str, ...]
    lexical_overlap: float = Field(ge=0, le=1)
    semantic_overlap: float = Field(ge=0, le=1)


class NoveltyResultV1(FrozenModel):
    schema_version: Literal[1] = 1
    novelty_result_id: str = Field(min_length=1, max_length=128)
    candidate_id: str
    verdict: NoveltyVerdict
    canonical_topic: str
    matched_content_ids: tuple[str, ...] = ()
    overlap_categories: tuple[str, ...] = ()
    cooldown_band: CooldownBand = CooldownBand.ELIGIBLE
    reasons: tuple[str, ...] = ()
    matches: tuple[NoveltyMatchV1, ...] = ()


class ContentPlanV1(FrozenModel):
    schema_version: Literal[1] = 1
    plan_id: str = Field(min_length=1, max_length=128)
    candidate_id: str
    profile_id: str
    profile_version: int = Field(ge=1)
    role: str
    canonical_topic: str
    subtopics: tuple[str, ...] = ()
    angle: str
    target_effect: str
    format: Literal["text", "single_image", "carousel", "infographic"]
    hook_pattern: str
    visual_pattern_hint: str | None = None
    novelty_result_ref: str
    planning_rationale: str


class DistributionSummary(FrozenModel):
    scheduled: int = Field(default=0, ge=0)
    published: int = Field(default=0, ge=0)
    needs_reconciliation: int = Field(default=0, ge=0)


class ContentItem(FrozenModel):
    content_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    canonical_topic: str
    subtopics: tuple[str, ...] = ()
    angle: str
    role: str
    target_effect: str
    format: Literal["text", "single_image", "carousel", "infographic"]
    hook_pattern: str
    visual_pattern: str | None = None
    editorial_state: ContentEditorialState = ContentEditorialState.PLANNED
    current_revision_id: None = None
    latest_approval_id: None = None
    distribution_summary: DistributionSummary = DistributionSummary()
    created_at: datetime
    updated_at: datetime


class EditorialMemoryEntry(FrozenModel):
    memory_id: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    lifecycle_source: LifecycleSource
    canonical_topic: str
    subtopics: tuple[str, ...] = ()
    angle: str
    hook_pattern: str
    role: str
    format: str
    visual_pattern: str | None = None
    entities: tuple[str, ...] = ()
    semantic_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_ref: str | None = None
    effective_at: datetime
    cooldown_until: datetime | None = None
    weight: float = Field(ge=0, le=1)
    created_at: datetime


class PersistedContentPlan(FrozenModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    plan: ContentPlanV1
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


_NON_WORD = re.compile(r"[^a-z0-9]+")
_TOKEN = re.compile(r"[a-z0-9]{2,}")


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(_NON_WORD.sub(" ", ascii_value).split())


def canonicalize_topic(value: str) -> str:
    normalized = normalize_text(value)
    aliases = {
        "tires": "automotive.tires",
        "tyres": "automotive.tires",
        "llantas": "automotive.tires",
        "neumaticos": "automotive.tires",
        "sql": "tech.sql",
        "databases": "tech.databases",
        "database": "tech.databases",
    }
    if normalized in aliases:
        return aliases[normalized]
    slug = ".".join(normalized.split())
    return slug[:160] or "general"


def lexical_tokens(*values: str) -> set[str]:
    normalized = normalize_text(" ".join(value for value in values if value))
    return set(_TOKEN.findall(normalized))


def semantic_fingerprint(*values: str) -> str:
    tokens = sorted(lexical_tokens(*values))
    payload = "|".join(tokens)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_sha256(payload: BaseModel | dict) -> str:
    value = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
