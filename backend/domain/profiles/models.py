from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AccountType(str, Enum):
    PERSONAL_BRAND = "personal_brand"
    BUSINESS = "business"
    EDUCATION = "education"
    NICHE = "niche"
    OTHER = "other"


class Goal(str, Enum):
    GROW = "grow"
    EDUCATE = "educate"
    BUILD_AUTHORITY = "build_authority"
    SELL = "sell"
    BUILD_COMMUNITY = "build_community"
    ENTERTAIN = "entertain"


class Channel(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    MANUAL_EXPORT = "manual_export"


class ProfileExampleInput(StrictModel):
    kind: Literal["caption", "bio"] = "caption"
    text: str = Field(min_length=1, max_length=12_000)
    label: str | None = Field(default=None, max_length=120)

    @field_validator("text")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("example text cannot be blank")
        return normalized


class ProfileSetup(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    account_type: AccountType
    goals: tuple[Goal, ...] = Field(min_length=1, max_length=6)
    audience: str = Field(min_length=2, max_length=800)
    voice: tuple[str, ...] = Field(min_length=1, max_length=6)
    voice_nuance: str | None = Field(default=None, max_length=280)
    batch_size: int = Field(default=4, ge=1, le=30)
    channels: tuple[Channel, ...] = Field(min_length=1, max_length=4)
    examples: tuple[ProfileExampleInput, ...] = Field(default=(), max_length=12)

    @field_validator("name", "audience", "voice_nuance")
    @classmethod
    def strip_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            if info.field_name == "voice_nuance":
                return None
            raise ValueError(f"{info.field_name} cannot be blank")
        return normalized

    @field_validator("voice")
    @classmethod
    def normalize_voice(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(item.strip().lower() for item in value if item.strip()))
        if not normalized:
            raise ValueError("at least one voice descriptor is required")
        return normalized


class Profile(FrozenModel):
    profile_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    current_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)
    status: ProfileStatus = ProfileStatus.ACTIVE
    created_at: datetime
    updated_at: datetime


class ProfileIdentity(FrozenModel):
    name: str
    account_type: AccountType
    summary: str


class EditorialStrategy(FrozenModel):
    topic_families: tuple[str, ...] = ()
    excluded_topics: tuple[str, ...] = ()


class NoveltyPolicy(FrozenModel):
    avoid_recent_repetition: bool = True
    default_cooldown_days: int = Field(default=7, ge=1, le=90)


class CopyPolicy(FrozenModel):
    voice_traits: tuple[str, ...]
    nuance: str | None = None
    target_language: Literal["es", "en", "pt"] = "es"
    caption_length_tendency: Literal["short", "medium", "long", "unknown"] = "unknown"
    hook_tendencies: tuple[str, ...] = ()
    cta_style: str | None = None
    min_words: int | None = Field(default=None, ge=40, le=1200)
    max_words: int | None = Field(default=None, ge=40, le=1200)

    @model_validator(mode="after")
    def valid_word_range(self):
        if self.min_words is not None and self.max_words is not None and self.min_words > self.max_words:
            raise ValueError("min_words cannot exceed max_words")
        return self


class ClaimPolicy(FrozenModel):
    forbidden_claims: tuple[str, ...] = ()
    safety_sensitivities: tuple[str, ...] = ()


class VisualSystem(FrozenModel):
    traits: tuple[str, ...] = ()


class PublishingPreferences(FrozenModel):
    channels: tuple[Channel, ...]
    default_batch_size: int


class AgentPolicy(FrozenModel):
    proposal_requires_human_acceptance: bool = True
    expose_model_configuration: bool = False


class InferenceEvidence(FrozenModel):
    kind: Literal["caption", "bio"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: str | None = None
    word_count: int = Field(ge=0)


class MigrationProvenance(FrozenModel):
    source: Literal["USER_ACCEPTED", "MK0_CONTENT_PROFILE"]
    source_profile_id: str | None = None
    source_version: int | None = None
    source_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ProfileVersion(FrozenModel):
    schema_version: Literal[2] = 2
    profile_id: str
    tenant_id: str
    version: int = Field(ge=1)
    identity: ProfileIdentity
    goals: tuple[Goal, ...]
    audience: tuple[str, ...]
    editorial_strategy: EditorialStrategy
    novelty_policy: NoveltyPolicy
    copy_policy: CopyPolicy
    claim_policy: ClaimPolicy
    visual_system: VisualSystem
    publishing_preferences: PublishingPreferences
    agent_policy: AgentPolicy
    inferred_from_examples: tuple[InferenceEvidence, ...] = ()
    provenance: MigrationProvenance
    accepted_at: datetime
    created_at: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    def snapshot(self) -> dict:
        return self.model_dump(mode="json")


class ProfileInferenceProposal(FrozenModel):
    schema_version: Literal[1] = 1
    setup_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_summary: str
    audience_segments: tuple[str, ...]
    topic_families: tuple[str, ...]
    hook_tendencies: tuple[str, ...]
    caption_length_tendency: Literal["short", "medium", "long", "unknown"]
    cta_style: str | None
    evidence: tuple[InferenceEvidence, ...]
    confidence: Literal["explicit_only", "low", "medium"]
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def canonical_digest(payload: BaseModel | dict) -> str:
    value = payload.model_dump(mode="json", exclude={"digest", "proposal_digest"}) if isinstance(payload, BaseModel) else payload
    def encode(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, Enum):
            return item.value
        raise TypeError(f"Unsupported canonical value: {type(item).__name__}")

    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=encode)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
