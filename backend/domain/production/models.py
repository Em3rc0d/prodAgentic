from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResearchVerdict(str, Enum):
    GO = "GO"
    GO_WITH_CAUTION = "GO_WITH_CAUTION"
    NO_GO = "NO_GO"


class ClaimCategory(str, Enum):
    FACTUAL = "factual"
    INTERPRETIVE = "interpretive"
    EXPERIENCE = "experience"
    PROMOTIONAL = "promotional"


class ClaimConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimPublishability(str, Enum):
    ALLOWED = "allowed"
    QUALIFY = "qualify"
    FORBIDDEN = "forbidden"


class EvidenceSourceType(str, Enum):
    WEB = "web"
    OFFICIAL_DOC = "official_doc"
    REPOSITORY = "repository"
    USER_PROVIDED = "user_provided"
    DATASET = "dataset"
    OTHER = "other"


class EvidenceTrustLevel(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTEXT = "context"


class EvidenceRefV1(FrozenModel):
    schema_version: Literal[1] = 1
    evidence_id: str = Field(min_length=1, max_length=128)
    source_type: EvidenceSourceType
    title: str = Field(min_length=1, max_length=500)
    locator: str | None = Field(default=None, max_length=2_000)
    observed_at: datetime | None = None
    trusted_level: EvidenceTrustLevel
    notes: str | None = Field(default=None, max_length=2_000)


class ClaimV1(FrozenModel):
    schema_version: Literal[1] = 1
    claim_id: str = Field(min_length=1, max_length=128)
    statement: str = Field(min_length=1, max_length=4_000)
    category: ClaimCategory
    confidence: ClaimConfidence
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=32)
    publishability: ClaimPublishability
    notes: str | None = Field(default=None, max_length=2_000)


class ResearchPackV1(FrozenModel):
    schema_version: Literal[1] = 1
    research_id: str = Field(min_length=1, max_length=128)
    plan_id: str = Field(min_length=1, max_length=128)
    verdict: ResearchVerdict
    key_points: tuple[str, ...] = Field(default=(), max_length=32)
    claims: tuple[ClaimV1, ...] = Field(default=(), max_length=64)
    evidence: tuple[EvidenceRefV1, ...] = Field(default=(), max_length=64)
    uncertainties: tuple[str, ...] = Field(default=(), max_length=32)
    safety_notes: tuple[str, ...] = Field(default=(), max_length=32)
    forbidden_claims: tuple[str, ...] = Field(default=(), max_length=32)
    recommended_angle: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def claim_evidence_refs_exist(self):
        evidence_ids = {item.evidence_id for item in self.evidence}
        for claim in self.claims:
            unknown = set(claim.evidence_refs) - evidence_ids
            if unknown:
                raise ValueError(f"claim {claim.claim_id} references unknown evidence IDs: {sorted(unknown)}")
        if len({item.claim_id for item in self.claims}) != len(self.claims):
            raise ValueError("claim IDs must be unique")
        if len(evidence_ids) != len(self.evidence):
            raise ValueError("evidence IDs must be unique")
        return self


class TextFormatSpecV1(FrozenModel):
    kind: Literal["text"] = "text"


class SingleImageSpecV1(FrozenModel):
    kind: Literal["single_image"] = "single_image"
    headline: str = Field(min_length=1, max_length=500)
    supporting_copy: tuple[str, ...] = Field(default=(), max_length=12)
    footer: str | None = Field(default=None, max_length=500)


class CarouselSlideV1(FrozenModel):
    slide_id: str = Field(min_length=1, max_length=128)
    role: Literal["hook", "explain", "evidence", "example", "takeaway", "cta"]
    headline: str = Field(min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=2_000)
    bullets: tuple[str, ...] = Field(default=(), max_length=12)


class CarouselSpecV1(FrozenModel):
    kind: Literal["carousel"] = "carousel"
    slides: tuple[CarouselSlideV1, ...] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def slide_ids_unique(self):
        ids = [item.slide_id for item in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("carousel slide IDs must be unique")
        return self


class InfographicSectionV1(FrozenModel):
    section_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=300)
    value_or_copy: str = Field(min_length=1, max_length=2_000)
    relationship: str | None = Field(default=None, max_length=500)


class InfographicSpecV1(FrozenModel):
    kind: Literal["infographic"] = "infographic"
    title: str = Field(min_length=1, max_length=500)
    sections: tuple[InfographicSectionV1, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def section_ids_unique(self):
        ids = [item.section_id for item in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("infographic section IDs must be unique")
        return self


FormatSpecV1 = TextFormatSpecV1 | SingleImageSpecV1 | CarouselSpecV1 | InfographicSpecV1


class ContentSpecV1(FrozenModel):
    schema_version: Literal[1] = 1
    content_spec_id: str = Field(min_length=1, max_length=128)
    plan_id: str = Field(min_length=1, max_length=128)
    language: Literal["es", "en", "pt"]
    title: str | None = Field(default=None, max_length=500)
    hook: str = Field(min_length=1, max_length=2_000)
    body: str = Field(min_length=1, max_length=30_000)
    cta: str | None = Field(default=None, max_length=2_000)
    hashtags: tuple[str, ...] = Field(default=(), max_length=30)
    alt_text_draft: str | None = Field(default=None, max_length=4_000)
    format: Literal["text", "single_image", "carousel", "infographic"]
    format_spec: FormatSpecV1
    claims_used: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def format_matches_spec(self):
        if self.format != self.format_spec.kind:
            raise ValueError("format must match format_spec.kind")
        if len(self.claims_used) != len(set(self.claims_used)):
            raise ValueError("claims_used must not contain duplicates")
        return self


class EditorialCheck(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class EditorialVerdict(str, Enum):
    APPROVE_TEXT = "APPROVE_TEXT"
    REVISE = "REVISE"
    REJECT = "REJECT"


class EditorialIssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class EditorialIssueV1(FrozenModel):
    code: str = Field(min_length=1, max_length=120)
    severity: EditorialIssueSeverity
    message: str = Field(min_length=1, max_length=2_000)
    target_ref: str | None = Field(default=None, max_length=256)


class EditorialReviewV1(FrozenModel):
    schema_version: Literal[1] = 1
    review_id: str = Field(min_length=1, max_length=128)
    verdict: EditorialVerdict
    brand_match: EditorialCheck
    clarity: EditorialCheck
    hook_strength: EditorialCheck
    factual_consistency: EditorialCheck
    platform_fit: EditorialCheck
    issues: tuple[EditorialIssueV1, ...] = Field(default=(), max_length=64)
    revised_content_spec: ContentSpecV1 | None = None

    @model_validator(mode="after")
    def revision_contract(self):
        if self.verdict == EditorialVerdict.REVISE and self.revised_content_spec is None:
            raise ValueError("REVISE requires revised_content_spec")
        if self.verdict == EditorialVerdict.APPROVE_TEXT and any(
            issue.severity == EditorialIssueSeverity.BLOCKING for issue in self.issues
        ):
            raise ValueError("APPROVE_TEXT cannot contain blocking issues")
        return self


class AgentKind(str, Enum):
    RESEARCH = "RESEARCH"
    WRITER = "WRITER"
    EDITOR = "EDITOR"
    VISUAL = "VISUAL"


class AgentAttemptStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CONTRACT_REPAIR = "CONTRACT_REPAIR"


class AgentAttemptEvidenceV1(FrozenModel):
    schema_version: Literal[1] = 1
    agent_run_id: str = Field(min_length=1, max_length=128)
    agent: AgentKind
    contract_version: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=240)
    attempt: int = Field(ge=1, le=20)
    latency_ms: int = Field(ge=0)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    status: AgentAttemptStatus
    safe_failure_code: str | None = Field(default=None, max_length=160)
    created_at: datetime


class GenerationRunState(str, Enum):
    CREATED = "CREATED"
    RESEARCHING = "RESEARCHING"
    WRITING = "WRITING"
    EDITING = "EDITING"
    VISUAL_PLANNING = "VISUAL_PLANNING"
    RENDERING = "RENDERING"
    QA = "QA"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationFailureV1(FrozenModel):
    code: str = Field(min_length=1, max_length=160)
    stage: str = Field(min_length=1, max_length=80)
    retryable: bool
    safe_message: str = Field(min_length=1, max_length=2_000)


class GenerationRunV1(FrozenModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    profile_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_id: str = Field(min_length=1, max_length=128)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: GenerationRunState
    contract_versions: tuple[str, ...]
    agent_run_refs: tuple[str, ...] = ()
    research_pack_ref: str | None = None
    content_spec_ref: str | None = None
    editorial_review_ref: str | None = None
    visual_spec_ref: str | None = None
    qa_report_refs: tuple[str, ...] = ()
    failure: GenerationFailureV1 | None = None
    started_at: datetime
    completed_at: datetime | None = None


class RevisionSource(str, Enum):
    GENERATION = "GENERATION"
    HUMAN_EDIT = "HUMAN_EDIT"
    REWRITE = "REWRITE"
    VISUAL_REGEN = "VISUAL_REGEN"


class RevisionStatus(str, Enum):
    DRAFT = "DRAFT"
    QA_PENDING = "QA_PENDING"
    REVIEWABLE = "REVIEWABLE"
    SUPERSEDED = "SUPERSEDED"


class ContentRevisionV1(FrozenModel):
    schema_version: Literal[1] = 1
    revision_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    parent_revision_id: str | None = Field(default=None, max_length=128)
    source: RevisionSource
    content_spec_ref: str = Field(min_length=1, max_length=128)
    content_spec_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    visual_spec_ref: str | None = Field(default=None, max_length=128)
    visual_spec_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    asset_refs: tuple[str, ...] = ()
    qa_report_id: str | None = Field(default=None, max_length=128)
    status: RevisionStatus = RevisionStatus.DRAFT
    created_at: datetime


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
