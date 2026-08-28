from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SourceAuthority(str, Enum):
    USER_PROVIDED = "USER_PROVIDED"
    SOURCE_SNAPSHOT = "SOURCE_SNAPSHOT"
    SYSTEM_DERIVED = "SYSTEM_DERIVED"
    EXTERNAL_PUBLICATION_EVIDENCE = "EXTERNAL_PUBLICATION_EVIDENCE"


class SourceType(str, Enum):
    PASTED_TEXT = "PASTED_TEXT"
    URL_SNAPSHOT = "URL_SNAPSHOT"
    DOCUMENT_EXCERPT = "DOCUMENT_EXCERPT"
    REPOSITORY_EXCERPT = "REPOSITORY_EXCERPT"
    USER_ASSERTION = "USER_ASSERTION"
    CI_EVIDENCE = "CI_EVIDENCE"
    APPROVAL_EVIDENCE = "APPROVAL_EVIDENCE"
    PUBLICATION_EVIDENCE = "PUBLICATION_EVIDENCE"


class ClaimType(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    OPINION = "OPINION"
    EXPERIENCE = "EXPERIENCE"
    ESTIMATE = "ESTIMATE"
    PREDICTION = "PREDICTION"


class GroundingStatus(str, Enum):
    GROUNDED = "GROUNDED"
    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
    OPINION = "OPINION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"


class GroundingDecision(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"


class GroundingReviewDecision(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class EvidenceRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceRef(BaseModel):
    evidence_id: str
    authority: SourceAuthority
    source_type: SourceType
    locator: Optional[str] = None
    excerpt: Optional[str] = Field(default=None, max_length=4000)
    content_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_id")
    @classmethod
    def require_evidence_id(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("evidence_id must not be blank")
        return value

    @field_validator("locator", "excerpt")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("content_sha256")
    @classmethod
    def require_sha256_hex(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("content_sha256 must be hexadecimal")
        return value

    @model_validator(mode="after")
    def require_inspectable_evidence(self):
        if self.locator is None and self.excerpt is None and self.content_sha256 is None:
            raise ValueError("evidence must include locator, excerpt, or content_sha256")
        return self


class SourcePacket(BaseModel):
    packet_id: str
    workspace_id: str
    title: str
    summary: Optional[str] = None
    strict_mode: bool = True
    evidence: list[EvidenceRef] = Field(default_factory=list)
    allowed_inferences: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("packet_id", "workspace_id", "title")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_unique_evidence_ids(self):
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_id values must be unique within a source packet")
        return self


class ClaimProposal(BaseModel):
    """Non-authoritative claim extraction output.

    A model/extractor may propose claim identity, wording and semantic type, but
    it cannot assign GroundingStatus. That authority belongs to the deterministic
    assessment builder and policy layers.
    """

    claim_id: str
    statement: str
    claim_type: ClaimType
    confidence: float = Field(ge=0.0, le=1.0)
    text_start: Optional[int] = Field(default=None, ge=0)
    text_end: Optional[int] = Field(default=None, ge=0)

    @field_validator("claim_id", "statement")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def require_valid_text_span(self):
        if (self.text_start is None) != (self.text_end is None):
            raise ValueError("text_start and text_end must be provided together")
        if self.text_start is not None and self.text_end <= self.text_start:
            raise ValueError("text_end must be greater than text_start")
        return self


class EvidenceMatchProposal(BaseModel):
    """Non-authoritative proposed relation between one claim and evidence."""

    claim_id: str
    evidence_id: str
    relation: EvidenceRelation
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("claim_id", "evidence_id")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.strip()
        return value or None


class GroundingEvaluationDraft(BaseModel):
    """Proposal envelope produced before authoritative GroundingAssessment."""

    draft_id: str
    packet_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    evaluator_version: str
    extraction_complete: bool
    claims: list[ClaimProposal] = Field(default_factory=list)
    evidence_matches: list[EvidenceMatchProposal] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("draft_id", "packet_id", "evaluator_version")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("content_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("content_sha256 must be hexadecimal")
        return value

    @model_validator(mode="after")
    def require_coherent_proposals(self):
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique within a grounding draft")

        known_claims = set(claim_ids)
        for match in self.evidence_matches:
            if match.claim_id not in known_claims:
                raise ValueError(
                    f"evidence match references unknown claim_id {match.claim_id}"
                )

        match_keys = [
            (match.claim_id, match.evidence_id, match.relation.value)
            for match in self.evidence_matches
        ]
        if len(match_keys) != len(set(match_keys)):
            raise ValueError("duplicate evidence relation proposals are not allowed")
        return self


class Claim(BaseModel):
    claim_id: str
    statement: str
    claim_type: ClaimType
    grounding_status: GroundingStatus
    source_refs: list[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("claim_id", "statement")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("source_refs")
    @classmethod
    def require_unique_source_refs(cls, value: list[str]):
        normalized = []
        for item in value:
            item = item.strip()
            if not item:
                raise ValueError("source_refs must not contain blank values")
            normalized.append(item)
        if len(normalized) != len(set(normalized)):
            raise ValueError("source_refs must be unique")
        return normalized

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def enforce_claim_semantics(self):
        allowed_statuses = {
            ClaimType.FACT: {
                GroundingStatus.GROUNDED,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
                GroundingStatus.CONTRADICTED,
            },
            ClaimType.EXPERIENCE: {
                GroundingStatus.GROUNDED,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
                GroundingStatus.CONTRADICTED,
            },
            ClaimType.INFERENCE: {
                GroundingStatus.SUPPORTED_INFERENCE,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
                GroundingStatus.CONTRADICTED,
            },
            ClaimType.ESTIMATE: {
                GroundingStatus.SUPPORTED_INFERENCE,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
                GroundingStatus.CONTRADICTED,
            },
            ClaimType.PREDICTION: {
                GroundingStatus.SUPPORTED_INFERENCE,
                GroundingStatus.INSUFFICIENT_EVIDENCE,
                GroundingStatus.CONTRADICTED,
            },
            ClaimType.OPINION: {GroundingStatus.OPINION},
        }
        if self.grounding_status not in allowed_statuses[self.claim_type]:
            raise ValueError(
                f"{self.claim_type.value} cannot use grounding status {self.grounding_status.value}"
            )

        if self.grounding_status in {
            GroundingStatus.GROUNDED,
            GroundingStatus.SUPPORTED_INFERENCE,
            GroundingStatus.CONTRADICTED,
        } and not self.source_refs:
            raise ValueError(f"{self.grounding_status.value} claims require source_refs")
        return self


class GroundingAssessment(BaseModel):
    assessment_id: str
    packet_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    evaluator_version: str
    extraction_complete: bool
    claims: list[Claim] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("assessment_id", "packet_id", "evaluator_version")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("content_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("content_sha256 must be hexadecimal")
        return value

    @model_validator(mode="after")
    def require_unique_claim_ids(self):
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique within an assessment")
        return self


class GroundingGateResult(BaseModel):
    policy_version: str
    decision: GroundingDecision
    blocking_claim_ids: list[str] = Field(default_factory=list)
    warning_claim_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class GroundingEvaluationRequest(BaseModel):
    source_packet: SourcePacket
    assessment: GroundingAssessment

    @model_validator(mode="after")
    def require_matching_packet_ids(self):
        if self.source_packet.packet_id != self.assessment.packet_id:
            raise ValueError("assessment packet_id must match source_packet packet_id")
        return self


class GroundingDraftEvaluationRequest(BaseModel):
    source_packet: SourcePacket
    draft: GroundingEvaluationDraft

    @model_validator(mode="after")
    def require_matching_packet_ids(self):
        if self.source_packet.packet_id != self.draft.packet_id:
            raise ValueError("draft packet_id must match source_packet packet_id")
        return self


class GroundingReviewRequest(BaseModel):
    decision: GroundingReviewDecision


class GroundingReviewSnapshot(BaseModel):
    review_id: str
    decision: GroundingReviewDecision
    source: str = "explicit_user_action"
    content_sha256: str = Field(min_length=64, max_length=64)
    source_packet_sha256: str = Field(min_length=64, max_length=64)
    assessment_sha256: str = Field(min_length=64, max_length=64)
    policy_version: str
    warning_claim_ids: list[str] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("review_id", "policy_version")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("content_sha256", "source_packet_sha256", "assessment_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("digest must be hexadecimal")
        return value
