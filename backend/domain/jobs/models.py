from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping


class DispatchState(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"


class ExecutionState(str, Enum):
    READY = "READY"
    CLAIMED = "CLAIMED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"


@dataclass(frozen=True)
class JobIntent:
    tenant_id: str
    job_id: str
    kind: str
    payload: Mapping[str, Any]
    payload_sha256: str
    created_at: datetime
    dispatch_state: DispatchState = DispatchState.PENDING
    execution_state: ExecutionState = ExecutionState.READY
    dispatch_attempts: int = 0
    execution_attempts: int = 0
    last_dispatched_at: datetime | None = None
    claimed_by: str | None = None
    claim_token: str | None = None
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    revision: int = 0

    @property
    def terminal(self) -> bool:
        return self.execution_state in {
            ExecutionState.SUCCEEDED,
            ExecutionState.DEAD_LETTERED,
        }


@dataclass(frozen=True)
class TransportMessage:
    message_id: str
    tenant_id: str
    job_id: str
    kind: str
    payload_sha256: str


@dataclass(frozen=True)
class ClaimResult:
    status: str
    job: JobIntent | None = None
    claim_token: str | None = None


@dataclass(frozen=True)
class DomainLagMetrics:
    dispatchable_count: int
    ready_count: int
    claimed_count: int
    failed_count: int
    dead_letter_count: int
    oldest_dispatchable_age_seconds: float


@dataclass(frozen=True)
class StreamLagMetrics:
    stream_length: int
    pending_count: int
    lag: int | None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def payload_digest(payload: Mapping[str, Any]) -> str:
    return sha256(canonical_payload_bytes(payload)).hexdigest()


def deterministic_job_id(
    *,
    tenant_id: str,
    kind: str,
    idempotency_key: str,
    payload: Mapping[str, Any],
) -> str:
    material = {
        "tenant_id": tenant_id,
        "kind": kind,
        "idempotency_key": idempotency_key,
        "payload_sha256": payload_digest(payload),
    }
    digest = sha256(canonical_payload_bytes(material)).hexdigest()
    return f"job_{digest[:32]}"
