from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256 = r"^[0-9a-f]{64}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    RECONNECT_REQUIRED = "RECONNECT_REQUIRED"
    NOT_CONNECTED = "NOT_CONNECTED"


class ScheduleState(str, Enum):
    SCHEDULED = "SCHEDULED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class PublicationState(str, Enum):
    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED_SAFE = "FAILED_SAFE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class PlatformCapabilityV1(FrozenModel):
    schema_version: Literal[1] = 1
    provider: Literal["linkedin"] = "linkedin"
    connected: bool
    can_publish: bool
    supports_text: bool = True
    supports_single_image: bool = True
    supports_multi_image: bool = False
    can_reconcile: bool = False
    external_identity: str | None = Field(default=None, max_length=256)
    api_version: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    observed_at: datetime
    reason: str | None = Field(default=None, max_length=500)


def _mongo_utc(value: datetime) -> datetime:
    """Normalize provider evidence to MongoDB's millisecond datetime precision.

    Receipt digests must survive persistence/rehydration byte-for-byte. PyMongo
    stores BSON datetimes at millisecond precision, so microseconds below that
    boundary cannot participate in immutable receipt identity.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


class PublicationReceiptV1(FrozenModel):
    schema_version: Literal[1] = 1
    provider: Literal["linkedin"] = "linkedin"
    external_post_id: str = Field(min_length=1, max_length=512)
    external_asset_ids: tuple[str, ...] = ()
    provider_api_version: str = Field(pattern=r"^[0-9]{6}$")
    received_at: datetime
    receipt_digest: str = Field(pattern=_SHA256)

    @field_validator("received_at", mode="before")
    @classmethod
    def normalize_received_at(cls, value):
        if isinstance(value, datetime):
            return _mongo_utc(value)
        return value

    @model_validator(mode="after")
    def verify_digest(self):
        expected = canonical_sha256(self, exclude={"receipt_digest"})
        if expected != self.receipt_digest:
            raise ValueError("PublicationReceiptV1 receipt_digest mismatch")
        return self


class ScheduleV1(FrozenModel):
    schema_version: Literal[1] = 1
    schedule_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    approval_id: str = Field(min_length=1, max_length=128)
    connection_id: str | None = Field(default=None, max_length=128)
    provider: Literal["linkedin", "manual_export"]
    destination: str = Field(min_length=1, max_length=256)
    scheduled_for: datetime
    timezone_context: str = Field(min_length=1, max_length=120)
    state: ScheduleState = ScheduleState.SCHEDULED
    job_key: str = Field(min_length=1, max_length=128)
    bundle_sha256: str = Field(pattern=_SHA256)
    created_at: datetime
    dispatched_at: datetime | None = None
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = Field(default=None, max_length=1000)


class PublicationV1(FrozenModel):
    schema_version: Literal[1] = 1
    publication_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    approval_id: str = Field(min_length=1, max_length=128)
    schedule_id: str | None = Field(default=None, max_length=128)
    provider: Literal["linkedin"] = "linkedin"
    connection_id: str = Field(min_length=1, max_length=128)
    destination: str = Field(min_length=1, max_length=256)
    state: PublicationState = PublicationState.PENDING
    idempotency_key: str = Field(pattern=_SHA256)
    attempt_id: str | None = Field(default=None, max_length=128)
    bundle_sha256: str = Field(pattern=_SHA256)
    external_post_id: str | None = Field(default=None, max_length=512)
    external_asset_ids: tuple[str, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    safe_error: str | None = Field(default=None, max_length=1000)
    reconciliation_reason: str | None = Field(default=None, max_length=1000)
    receipt_digest: str | None = Field(default=None, pattern=_SHA256)
    provider_receipt: PublicationReceiptV1 | None = None

    @model_validator(mode="after")
    def published_requires_receipt(self):
        if self.state is PublicationState.PUBLISHED:
            if self.provider_receipt is None or self.receipt_digest != self.provider_receipt.receipt_digest:
                raise ValueError("PUBLISHED PublicationV1 requires matching provider receipt evidence")
            if self.external_post_id != self.provider_receipt.external_post_id:
                raise ValueError("Publication external_post_id must match provider receipt")
        return self


def _json_default(item):
    if isinstance(item, datetime):
        value = _mongo_utc(item).isoformat(timespec="milliseconds")
        return value[:-6] + "Z" if value.endswith("+00:00") else value
    if isinstance(item, Enum):
        return item.value
    return str(item)


def _canonical(value) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def canonical_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(exclude=exclude or set())
    return hashlib.sha256(_canonical(payload)).hexdigest()


def publication_operation_key(
    *,
    tenant_id: str,
    approval_id: str,
    bundle_sha256: str,
    provider: str,
    external_identity: str,
    destination: str,
    operation_version: str = "publish-v1",
) -> str:
    material = {
        "operation_version": operation_version,
        "tenant_id": tenant_id,
        "approval_id": approval_id,
        "bundle_sha256": bundle_sha256,
        "provider": provider,
        "external_identity": external_identity,
        "destination": destination,
    }
    return hashlib.sha256(_canonical(material)).hexdigest()


def deterministic_publication_id(idempotency_key: str) -> str:
    return f"pub_{idempotency_key[:40]}"


def deterministic_schedule_id(
    *,
    tenant_id: str,
    approval_id: str,
    connection_id: str | None,
    provider: str,
    destination: str,
    scheduled_for: datetime,
    bundle_sha256: str,
) -> str:
    material = {
        "tenant_id": tenant_id,
        "approval_id": approval_id,
        "connection_id": connection_id,
        "provider": provider,
        "destination": destination,
        "scheduled_for": scheduled_for,
        "bundle_sha256": bundle_sha256,
        "operation_version": "schedule-v1",
    }
    return f"sched_{hashlib.sha256(_canonical(material)).hexdigest()[:40]}"
