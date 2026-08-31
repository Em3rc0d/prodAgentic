from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContentFamily(str, Enum):
    BUILD_IN_PUBLIC = "BUILD_IN_PUBLIC"
    TECHNICAL_INSIGHT = "TECHNICAL_INSIGHT"
    CONTRARIAN_OBSERVATION = "CONTRARIAN_OBSERVATION"
    FAILURE_LESSON = "FAILURE_LESSON"
    ARCHITECTURE_DECISION = "ARCHITECTURE_DECISION"
    MINI_CASE_STUDY = "MINI_CASE_STUDY"
    PERSONAL_LEARNING = "PERSONAL_LEARNING"
    PRODUCT_PHILOSOPHY = "PRODUCT_PHILOSOPHY"
    BEFORE_AFTER = "BEFORE_AFTER"
    RESEARCH_SYNTHESIS = "RESEARCH_SYNTHESIS"


class AngleProviderCandidate(BaseModel):
    """Untrusted provider proposal for editorial framing only."""

    model_config = ConfigDict(extra="forbid")

    content_family: ContentFamily
    angle: str = Field(min_length=1, max_length=1200)
    hook_direction: str = Field(min_length=1, max_length=600)
    reader_tension: str = Field(min_length=1, max_length=600)
    reader_payoff: str = Field(min_length=1, max_length=600)
    evidence_statement_refs: list[str] = Field(default_factory=list, max_length=20)
    audience_relevance: float = Field(ge=0.0, le=1.0)
    distinctiveness: float = Field(ge=0.0, le=1.0)
    specificity: float = Field(ge=0.0, le=1.0)
    profile_curiosity: float = Field(ge=0.0, le=1.0)
    evidence_density: float = Field(ge=0.0, le=1.0)
    spam_risk: float = Field(ge=0.0, le=1.0)
    ai_slop_risk: float = Field(ge=0.0, le=1.0)

    @field_validator("angle", "hook_direction", "reader_tension", "reader_payoff")
    @classmethod
    def normalize_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("angle text must not be blank")
        return value

    @field_validator("evidence_statement_refs")
    @classmethod
    def normalize_refs(cls, value: list[str]):
        normalized = []
        for item in value:
            item = item.strip()
            if not item:
                raise ValueError("evidence_statement_refs must not contain blanks")
            normalized.append(item)
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence_statement_refs must be unique")
        return normalized


class AngleProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[AngleProviderCandidate] = Field(min_length=3, max_length=5)


class AngleCandidate(AngleProviderCandidate):
    candidate_id: str

    @field_validator("candidate_id")
    @classmethod
    def require_candidate_id(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("candidate_id must not be blank")
        return value


class AngleEngineOutput(BaseModel):
    output_id: str
    idea_sha256: str = Field(min_length=64, max_length=64)
    research_sha256: str = Field(min_length=64, max_length=64)
    factual_envelope_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)
    engine_version: str
    candidates: list[AngleCandidate] = Field(min_length=3, max_length=5)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("output_id", "engine_version")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("idea_sha256", "research_sha256", "factual_envelope_sha256")
    @classmethod
    def require_hex(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("digest must be hexadecimal")
        return value

    @model_validator(mode="after")
    def require_unique_candidates(self):
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique")
        return self


class AngleSelectionSnapshot(BaseModel):
    selection_id: str
    output_id: str
    selected_candidate_id: str
    selection_policy_version: str
    selected_score: float = Field(ge=0.0, le=1.0)
    selected_candidate: AngleCandidate
    alternatives: list[AngleCandidate] = Field(default_factory=list, max_length=4)
    idea_sha256: str = Field(min_length=64, max_length=64)
    research_sha256: str = Field(min_length=64, max_length=64)
    factual_envelope_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AttentionCriticProviderResponse(BaseModel):
    """Untrusted editorial-quality assessment. Never factual authority."""

    model_config = ConfigDict(extra="forbid")

    hook: float = Field(ge=0.0, le=1.0)
    idea_clarity: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    specificity: float = Field(ge=0.0, le=1.0)
    credibility_signal: float = Field(ge=0.0, le=1.0)
    narrative_progression: float = Field(ge=0.0, le=1.0)
    payoff: float = Field(ge=0.0, le=1.0)
    human_voice: float = Field(ge=0.0, le=1.0)
    conversation_potential: float = Field(ge=0.0, le=1.0)
    profile_curiosity: float = Field(ge=0.0, le=1.0)
    spam_risk: float = Field(ge=0.0, le=1.0)
    ai_slop_risk: float = Field(ge=0.0, le=1.0)
    engagement_bait_detected: bool = False
    generic_opening_detected: bool = False
    strengths: list[str] = Field(default_factory=list, max_length=8)
    rewrite_directives: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("strengths", "rewrite_directives")
    @classmethod
    def normalize_list(cls, value: list[str]):
        normalized = []
        for item in value:
            item = item.strip()
            if item:
                normalized.append(item)
        return normalized


class AttentionCriticAssessment(AttentionCriticProviderResponse):
    assessment_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    critic_version: str
    pass_number: int = Field(ge=1, le=2)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("assessment_id", "critic_version")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class ContentQualityDecision(str, Enum):
    PASS = "PASS"
    REWRITE = "REWRITE"


class ContentQualityGate(BaseModel):
    policy_version: str
    decision: ContentQualityDecision
    editorial_score: float = Field(ge=0.0, le=1.0)
    hard_flags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ContentQualitySnapshot(BaseModel):
    content_sha256: str = Field(min_length=64, max_length=64)
    assessment: AttentionCriticAssessment
    gate: ContentQualityGate
    rewrite_performed: bool = False
    max_auto_rewrites: int = 1
    advisory_only: bool = True
    factual_score: None = None
    combined_factual_editorial_score: None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
