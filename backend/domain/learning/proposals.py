from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .models import ConfidenceBand, FrozenModel, PerformanceDimension, canonical_sha256

LEARNING_PROPOSAL_POLICY_VERSION = "r4-learning-proposal-v1"
_SHA256 = r"^[0-9a-f]{64}$"


class LearningProposalType(str, Enum):
    PROMOTE_TOPIC_FAMILY = "PROMOTE_TOPIC_FAMILY"
    PREFER_HOOK_TENDENCY = "PREFER_HOOK_TENDENCY"


class LearningRiskClass(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    SEMANTIC = "SEMANTIC"


class LearningDecisionValue(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class LearningProposalV1(FrozenModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    proposal_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    profile_digest: str = Field(pattern=_SHA256)
    summary_id: str = Field(min_length=1, max_length=128)
    summary_digest: str = Field(pattern=_SHA256)
    signal_id: str = Field(min_length=1, max_length=128)
    proposal_type: LearningProposalType
    dimension: PerformanceDimension
    proposed_value: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=600)
    confidence: ConfidenceBand
    sample_size: int = Field(ge=5)
    lift: float = Field(gt=0, le=1)
    risk_class: LearningRiskClass
    state: Literal["PROPOSED"] = "PROPOSED"
    policy_version: Literal["r4-learning-proposal-v1"] = LEARNING_PROPOSAL_POLICY_VERSION
    created_at: datetime
    proposal_digest: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_authority(self):
        if self.confidence not in {ConfidenceBand.MEDIUM, ConfidenceBand.HIGH}:
            raise ValueError("LearningProposal requires medium/high-confidence evidence")
        if self.dimension is PerformanceDimension.CANONICAL_TOPIC:
            if self.proposal_type is not LearningProposalType.PROMOTE_TOPIC_FAMILY:
                raise ValueError("canonical topic signals must map to PROMOTE_TOPIC_FAMILY")
            if self.risk_class is not LearningRiskClass.SEMANTIC:
                raise ValueError("topic-family promotion is a semantic proposal")
        elif self.dimension is PerformanceDimension.HOOK_PATTERN:
            if self.proposal_type is not LearningProposalType.PREFER_HOOK_TENDENCY:
                raise ValueError("hook signals must map to PREFER_HOOK_TENDENCY")
            if self.risk_class is not LearningRiskClass.OPERATIONAL:
                raise ValueError("hook-tendency preference is an operational proposal")
        else:
            raise ValueError("R4 learning proposals only support topic and hook dimensions")
        expected = canonical_sha256(self, exclude={"proposal_digest"})
        if expected != self.proposal_digest:
            raise ValueError("LearningProposalV1 proposal_digest mismatch")
        return self


class HumanProfileDecisionV1(FrozenModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    decision_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    proposal_id: str = Field(min_length=1, max_length=128)
    proposal_digest: str = Field(pattern=_SHA256)
    decision: LearningDecisionValue
    expected_current_version: int = Field(ge=1)
    target_profile_version: int | None = Field(default=None, ge=2)
    decided_at: datetime
    decision_digest: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_decision(self):
        expected_target = self.expected_current_version + 1
        if self.decision is LearningDecisionValue.ACCEPTED:
            if self.target_profile_version != expected_target:
                raise ValueError("accepted decision must bind the next ProfileVersion")
        elif self.target_profile_version is not None:
            raise ValueError("rejected decision cannot bind a target ProfileVersion")
        expected = canonical_sha256(self, exclude={"decision_digest"})
        if expected != self.decision_digest:
            raise ValueError("HumanProfileDecisionV1 decision_digest mismatch")
        return self


def deterministic_learning_proposal_id(
    *,
    tenant_id: str,
    profile_id: str,
    profile_digest: str,
    summary_digest: str,
    proposal_type: LearningProposalType,
    proposed_value: str,
) -> str:
    material = "|".join(
        (
            LEARNING_PROPOSAL_POLICY_VERSION,
            tenant_id,
            profile_id,
            profile_digest,
            summary_digest,
            proposal_type.value,
            proposed_value,
        )
    )
    return f"learn_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"


def deterministic_learning_decision_id(
    *,
    proposal_id: str,
    proposal_digest: str,
    decision: LearningDecisionValue,
    expected_current_version: int,
) -> str:
    material = "|".join(
        (
            LEARNING_PROPOSAL_POLICY_VERSION,
            proposal_id,
            proposal_digest,
            decision.value,
            str(expected_current_version),
        )
    )
    return f"decision_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"
