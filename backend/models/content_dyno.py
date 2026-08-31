from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrustWheelStatus(str, Enum):
    NOT_MEASURED = "NOT_MEASURED"
    PASS = "PASS"
    FAIL = "FAIL"


class EditorialVerdict(str, Enum):
    DO_NOT_PUBLISH = "DO_NOT_PUBLISH"
    PUBLISHABLE = "PUBLISHABLE"
    STRONG = "STRONG"
    EXCELLENT = "EXCELLENT"
    WOULD_PUBLISH_NOW = "WOULD_PUBLISH_NOW"


class DynoSignature(str, Enum):
    UNSIGNED = "UNSIGNED"
    TRUST_FAIL = "TRUST_FAIL"
    SIGNED_PASS = "SIGNED_PASS"


class LossSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HumanEditorialReview(BaseModel):
    """Explicit human product judgement bound to the exact reviewed asset.

    The subjective scores remain human authority. The identity fields make that
    authority revision-bound so a verdict cannot silently migrate to another
    ContentRun, text revision, or visual asset.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=200)
    final_content_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    visual_asset_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    topic_fidelity: float = Field(ge=0.0, le=1.0)
    pov_strength: float = Field(ge=0.0, le=1.0)
    human_voice: float = Field(ge=0.0, le=1.0)
    usefulness: float = Field(ge=0.0, le=1.0)
    visual_message_fit: float = Field(ge=0.0, le=1.0)
    publish_readiness: float = Field(ge=0.0, le=1.0)
    verdict: EditorialVerdict
    notes: list[str] = Field(default_factory=list, max_length=12)
    source: str = "explicit_human_review"
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: list[str]):
        return [item.strip() for item in value if item.strip()]


class EditorialSensorSnapshot(BaseModel):
    """Internal advisory sensors only; never the product verdict."""

    editorial_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    decision: Optional[str] = None
    pass_number: Optional[int] = Field(default=None, ge=1, le=2)
    hook: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    idea_clarity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    novelty: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    specificity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    credibility_signal: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    narrative_progression: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    payoff: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    human_voice: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    conversation_potential: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    profile_curiosity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    spam_risk: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ai_slop_risk: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    hard_flags: list[str] = Field(default_factory=list)


class DrivetrainLoss(BaseModel):
    code: str
    layer: str
    severity: LossSeverity
    detail: str


class TrustWheelReport(BaseModel):
    status: TrustWheelStatus
    grounding_decision: Optional[str] = None
    grounding_policy_version: Optional[str] = None
    human_grounding_verified: bool = False
    blocking_claim_ids: list[str] = Field(default_factory=list)
    warning_claim_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ContentDynoCaseReport(BaseModel):
    dyno_version: str
    run_id: str
    topic: str
    style: str
    final_content_sha256: Optional[str] = None
    generation_source_packet_id: Optional[str] = None
    content_profile_id: Optional[str] = None
    angle_family: Optional[str] = None
    final_status: Optional[str] = None
    visual_provider: Optional[str] = None
    visual_asset_sha256: Optional[str] = None
    editorial_sensors: EditorialSensorSnapshot
    trust_at_wheels: TrustWheelReport
    drivetrain_losses: list[DrivetrainLoss] = Field(default_factory=list)
    human_review: Optional[HumanEditorialReview] = None
    signature: DynoSignature
    signature_reasons: list[str] = Field(default_factory=list)
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentDynoBatchReport(BaseModel):
    dyno_version: str
    case_count: int = Field(ge=1)
    signed_pass_count: int = Field(ge=0)
    trust_fail_count: int = Field(ge=0)
    unsigned_count: int = Field(ge=0)
    would_publish_now_count: int = Field(ge=0)
    would_publish_now_rate: float = Field(ge=0.0, le=1.0)
    loss_frequency: dict[str, int] = Field(default_factory=dict)
    reports: list[ContentDynoCaseReport]
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
