from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[0-9a-f]{64}$"
PROFILE_UPGRADE_POLICY_VERSION = "r4-profile-upgrade-v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _json_default(value):
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        normalized = normalized.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")


def _canonical_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json", exclude=exclude or set())
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ProfileUpgradeDecisionValue(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ProfileUpgradeProposalV1(FrozenModel):
    schema_version: Literal[1] = 1
    proposal_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    profile_digest: str = Field(pattern=_SHA256)
    removed_topic_families: tuple[str, ...] = Field(min_length=1, max_length=12)
    proposed_topic_families: tuple[str, ...] = Field(min_length=1, max_length=12)
    reason_codes: tuple[Literal["MALFORMED_TOPIC_FAMILY"], ...] = ("MALFORMED_TOPIC_FAMILY",)
    policy_version: Literal["r4-profile-upgrade-v1"] = PROFILE_UPGRADE_POLICY_VERSION
    proposal_digest: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_digest(self):
        if any(item in self.proposed_topic_families for item in self.removed_topic_families):
            raise ValueError("Profile upgrade cannot preserve a removed malformed topic verbatim")
        expected = _canonical_sha256(self, exclude={"proposal_digest"})
        if expected != self.proposal_digest:
            raise ValueError("ProfileUpgradeProposalV1 proposal_digest mismatch")
        return self


class HumanProfileUpgradeDecisionV1(FrozenModel):
    schema_version: Literal[1] = 1
    decision_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    proposal_id: str = Field(min_length=1, max_length=128)
    proposal_digest: str = Field(pattern=_SHA256)
    decision: ProfileUpgradeDecisionValue
    expected_current_version: int = Field(ge=1)
    target_profile_version: int | None = Field(default=None, ge=2)
    decided_at: datetime
    decision_digest: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_decision(self):
        expected_target = self.expected_current_version + 1
        if self.decision is ProfileUpgradeDecisionValue.ACCEPTED:
            if self.target_profile_version != expected_target:
                raise ValueError("accepted upgrade must bind the next ProfileVersion")
        elif self.target_profile_version is not None:
            raise ValueError("rejected upgrade cannot bind a target ProfileVersion")
        expected = _canonical_sha256(self, exclude={"decision_digest"})
        if expected != self.decision_digest:
            raise ValueError("HumanProfileUpgradeDecisionV1 decision_digest mismatch")
        return self


def malformed_topic_family(value: str) -> bool:
    words = re.findall(r"[\w'-]+", value.strip(), flags=re.UNICODE)
    return len(value.strip()) > 96 or len(words) > 6 or any(mark in value for mark in ("\n", ".", "?", "!"))


def deterministic_profile_upgrade_proposal_id(*, profile_id: str, profile_digest: str, proposed_topics: tuple[str, ...]) -> str:
    material = "|".join((PROFILE_UPGRADE_POLICY_VERSION, profile_id, profile_digest, *proposed_topics))
    return f"upgrade_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"


def deterministic_profile_upgrade_decision_id(*, proposal_id: str, proposal_digest: str, decision: ProfileUpgradeDecisionValue, expected_current_version: int) -> str:
    material = "|".join((PROFILE_UPGRADE_POLICY_VERSION, proposal_id, proposal_digest, decision.value, str(expected_current_version)))
    return f"upgrade_decision_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:40]}"


def profile_upgrade_digest(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    return _canonical_sha256(payload, exclude=exclude)
