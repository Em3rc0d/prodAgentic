from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QACheckLayer(str, Enum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    VISUAL = "visual"


class QASeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class QAVerdict(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    LAYOUT_RECOMPOSE = "LAYOUT_RECOMPOSE"
    REWRITE_COPY = "REWRITE_COPY"
    VISUAL_REGEN = "VISUAL_REGEN"
    ESCALATE = "ESCALATE"


class QACheckV1(FrozenModel):
    schema_version: Literal[1] = 1
    code: str = Field(min_length=1, max_length=160)
    layer: QACheckLayer
    severity: QASeverity
    passed: bool
    message: str = Field(min_length=1, max_length=2_000)
    target_ref: str | None = Field(default=None, max_length=256)
    recovery_hint: RecoveryAction = RecoveryAction.NONE


class VisualQAObservationV1(FrozenModel):
    schema_version: Literal[1] = 1
    page_index: int = Field(ge=0, le=19)
    clipping: bool = False
    overlap: bool = False
    unreadable_hierarchy: bool = False
    malformed_imagery: bool = False
    wrong_visible_text: bool = False
    key_copy_omitted: bool = False
    duplicate_page: bool = False
    semantic_contradiction: bool = False


class RecoveryDecisionV1(FrozenModel):
    schema_version: Literal[1] = 1
    action: RecoveryAction
    attempt: int = Field(ge=0, le=20)
    budget: int = Field(ge=0, le=20)
    exhausted: bool
    preserves_content: bool
    reason: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.attempt > self.budget and not self.exhausted:
            raise ValueError("recovery attempt beyond budget must be exhausted")
        if self.action == RecoveryAction.LAYOUT_RECOMPOSE and not self.preserves_content:
            raise ValueError("layout recompose must preserve valid content authority")
        return self


class QAReportV1(FrozenModel):
    schema_version: Literal[1] = 1
    qa_report_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    policy_version: Literal["qa-policy-v1"] = "qa-policy-v1"
    deterministic_checks: tuple[QACheckV1, ...] = ()
    semantic_checks: tuple[QACheckV1, ...] = ()
    visual_checks: tuple[QACheckV1, ...] = ()
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    verdict: QAVerdict
    content_spec_digest: str = Field(pattern=_SHA256_PATTERN)
    render_input_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    asset_digests: tuple[str, ...] = ()
    recovery_attempt: int = Field(default=0, ge=0, le=20)
    created_at: datetime
    digest: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def verdict_matches_checks(self):
        checks = self.deterministic_checks + self.semantic_checks + self.visual_checks
        blocking = [check for check in checks if not check.passed and check.severity == QASeverity.BLOCKING]
        warnings = [check for check in checks if not check.passed and check.severity == QASeverity.WARNING]
        if blocking and self.verdict != QAVerdict.FAIL:
            raise ValueError("blocking QA failures require FAIL verdict")
        if not blocking and warnings and self.verdict != QAVerdict.PASS_WITH_WARNINGS:
            raise ValueError("non-blocking QA warnings require PASS_WITH_WARNINGS")
        if not blocking and not warnings and self.verdict != QAVerdict.PASS:
            raise ValueError("clean QA checks require PASS")
        if tuple(check.code for check in blocking) != self.failures:
            raise ValueError("QA failures must exactly enumerate blocking failed check codes")
        if tuple(check.code for check in warnings) != self.warnings:
            raise ValueError("QA warnings must exactly enumerate warning failed check codes")
        return self


def canonical_qa_sha256(payload: BaseModel | dict) -> str:
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
