from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.grounding import ClaimType


class RemediationAction(str, Enum):
    KEEP = "KEEP"
    SOFTEN = "SOFTEN"
    REMOVE = "REMOVE"


class ClaimRemediationProposal(BaseModel):
    """Non-authoritative proposal for handling one blocked claim.

    A remediation proposal never changes Grounding state. SOFTEN creates new
    candidate wording that must pass the complete Grounding lifecycle again.
    """

    claim_id: str
    action: RemediationAction
    proposed_statement: Optional[str] = Field(default=None, max_length=4000)
    proposed_claim_type: Optional[ClaimType] = None
    source_refs: list[str] = Field(default_factory=list)
    rationale: Optional[str] = Field(default=None, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("claim_id")
    @classmethod
    def require_claim_id(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("claim_id must not be blank")
        return value

    @field_validator("proposed_statement", "rationale")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("source_refs")
    @classmethod
    def normalize_source_refs(cls, value: list[str]):
        normalized = []
        for item in value:
            item = item.strip()
            if not item:
                raise ValueError("source_refs must not contain blank values")
            normalized.append(item)
        if len(normalized) != len(set(normalized)):
            raise ValueError("source_refs must be unique")
        return normalized

    @model_validator(mode="after")
    def enforce_action_contract(self):
        if self.action == RemediationAction.SOFTEN:
            if self.proposed_statement is None or self.proposed_claim_type is None:
                raise ValueError("SOFTEN requires proposed_statement and proposed_claim_type")
            if self.proposed_claim_type == ClaimType.OPINION:
                if self.source_refs:
                    raise ValueError("SOFTEN to OPINION must not borrow factual source authority")
            elif not self.source_refs:
                raise ValueError("SOFTEN to a factual/inference claim type requires source_refs")
        else:
            if self.proposed_statement is not None or self.proposed_claim_type is not None:
                raise ValueError(f"{self.action.value} must not hide replacement wording")
            if self.source_refs:
                raise ValueError(f"{self.action.value} does not accept source_refs")
        return self


class RemediatorProviderResponse(BaseModel):
    """Narrow untrusted provider payload for blocked-claim remediation.

    The provider may suggest wording/actions only. Revision identity, evidence
    identity digests, assessment identity and all Grounding authority remain
    server-owned outside this schema.
    """

    model_config = ConfigDict(extra="forbid")

    proposals: list[ClaimRemediationProposal] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def require_unique_claim_proposals(self):
        claim_ids = [proposal.claim_id for proposal in self.proposals]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("only one provider remediation proposal is allowed per claim")
        return self


class GroundingRemediationDraft(BaseModel):
    remediation_id: str
    packet_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    source_packet_sha256: str = Field(min_length=64, max_length=64)
    assessment_id: str
    assessment_sha256: str = Field(min_length=64, max_length=64)
    remediator_version: str
    proposals: list[ClaimRemediationProposal] = Field(default_factory=list)

    @field_validator("remediation_id", "packet_id", "assessment_id", "remediator_version")
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

    @model_validator(mode="after")
    def require_unique_claim_proposals(self):
        claim_ids = [proposal.claim_id for proposal in self.proposals]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("only one remediation proposal is allowed per claim")
        return self


class RemediationGateResult(BaseModel):
    policy_version: str
    valid: bool
    blocking_claim_ids: list[str] = Field(default_factory=list)
    proposed_actions: dict[str, RemediationAction] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    requires_regrounding: bool = False
