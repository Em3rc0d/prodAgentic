from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[0-9a-f]{64}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApprovalAssetV2(FrozenModel):
    asset_id: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=_SHA256)


class ApprovalBundleV2(FrozenModel):
    schema_version: Literal[2] = 2
    approval_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    profile_snapshot_digest: str = Field(pattern=_SHA256)
    plan_digest: str = Field(pattern=_SHA256)
    research_digest: str = Field(pattern=_SHA256)
    content_digest: str = Field(pattern=_SHA256)
    visual_spec_digest: str | None = Field(default=None, pattern=_SHA256)
    assets: tuple[ApprovalAssetV2, ...] = ()
    qa_digest: str = Field(pattern=_SHA256)
    policy_version: str = Field(min_length=1, max_length=120)
    approved_by: str = Field(min_length=1, max_length=256)
    approved_at: datetime
    bundle_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_bundle_digest(self):
        expected = canonical_approval_sha256(self, exclude={"bundle_sha256"})
        if expected != self.bundle_sha256:
            raise ValueError("ApprovalBundleV2 bundle_sha256 mismatch")
        if len({asset.asset_id for asset in self.assets}) != len(self.assets):
            raise ValueError("ApprovalBundleV2 asset IDs must be unique")
        return self


class ApprovalReservationV1(FrozenModel):
    schema_version: Literal[1] = 1
    approval_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    review_digest: str = Field(pattern=_SHA256)
    approved_by: str = Field(min_length=1, max_length=256)
    approved_at: datetime


class ReviewAuthoritySnapshotV1(FrozenModel):
    schema_version: Literal[1] = 1
    tenant_id: str = Field(min_length=1, max_length=128)
    content_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    review_digest: str = Field(pattern=_SHA256)
    revision_status: Literal["REVIEWABLE"]
    editorial_state: str = Field(min_length=1, max_length=80)
    approval_available: bool
    existing_approval_id: str | None = Field(default=None, max_length=128)
    profile_snapshot_digest: str = Field(pattern=_SHA256)
    plan_digest: str = Field(pattern=_SHA256)
    research_digest: str = Field(pattern=_SHA256)
    content_digest: str = Field(pattern=_SHA256)
    visual_spec_digest: str | None = Field(default=None, pattern=_SHA256)
    qa_digest: str = Field(pattern=_SHA256)
    asset_digests: tuple[str, ...] = ()
    content: dict


def canonical_approval_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        value = payload.model_dump(mode="json", exclude=exclude or set())
    else:
        value = payload
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_default(value):
    if isinstance(value, datetime):
        serialized = value.isoformat()
        return serialized[:-6] + "Z" if serialized.endswith("+00:00") else serialized
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")
