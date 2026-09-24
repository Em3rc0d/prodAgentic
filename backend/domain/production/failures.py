"""Allowlisted durable failures: provider messages are never authority."""
from enum import Enum


class ProductionRecoveryAction(str, Enum):
    RETRY_PRODUCTION = "RETRY_PRODUCTION"
    REPLAN_CONTENT = "REPLAN_CONTENT"
    RESUME_PIPELINE = "RESUME_PIPELINE"
    HUMAN_ACTION_REQUIRED = "HUMAN_ACTION_REQUIRED"
    NONE = "NONE"


TRANSIENT_CODES = frozenset({
    "MODEL_TIMEOUT", "STAGE_TIMEOUT", "TIMEOUT", "SERVICE_UNAVAILABLE", "RATE_LIMITED",
    "QUOTA_EXHAUSTED", "PROVIDER_PROTOCOL_ERROR", "MODEL_NOT_FOUND", "MODEL_MISMATCH",
})
SEMANTIC_CODES = frozenset({"RESEARCH_NO_GO", "EDITOR_REJECTED", "EDITOR_REVISION_BUDGET_EXHAUSTED"})
SAFE_CODES = TRANSIENT_CODES | SEMANTIC_CODES | frozenset({
    "AUTHENTICATION", "INVALID_REQUEST", "CANCELLED", "UNKNOWN", "LANGUAGE_MISMATCH",
    "STRUCTURED_REPAIR_EXHAUSTED", "STRUCTURED_CONTRACT_INVALID", "ROUTING_EXHAUSTED",
    "LINEAGE_PROTOCOL_ERROR", "NO_COMPLETED_ATTEMPT", "STREAM_ENDED_WITHOUT_COMPLETION",
    "EVIDENCE_PROVIDER_UNAVAILABLE", "EVIDENCE_CONTRACT_VIOLATION", "PRODUCTION_INTERNAL_ERROR",
    "RESEARCH_CONTRACT_VIOLATION", "WRITER_CONTRACT_VIOLATION", "EDITOR_CONTRACT_VIOLATION",
    "EDITOR_REVISION_CONTRACT_VIOLATION", "EDITOR_REVISION_MISSING", "EDITOR_TERMINAL_VERDICT_MISSING",
    "RESEARCH_AGENT_FAILED", "WRITER_AGENT_FAILED", "EDITOR_AGENT_FAILED",
})


def recovery_for(code: str) -> ProductionRecoveryAction:
    if code in TRANSIENT_CODES:
        return ProductionRecoveryAction.RETRY_PRODUCTION
    if code in SEMANTIC_CODES:
        return ProductionRecoveryAction.REPLAN_CONTENT
    if code == "CANCELLED":
        return ProductionRecoveryAction.NONE
    return ProductionRecoveryAction.HUMAN_ACTION_REQUIRED


def safe_exception_code(exc: Exception, default: str) -> str:
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(getattr(exc, "category", None), "value", None)
    if isinstance(exc, TimeoutError):
        code = "STAGE_TIMEOUT"
    return code if code in SAFE_CODES else default


def failure_message(code: str) -> str:
    if code in {"MODEL_TIMEOUT", "STAGE_TIMEOUT", "TIMEOUT"}:
        return "Provider timed out."
    if code == "RESEARCH_NO_GO":
        return "Reliable evidence was insufficient."
    if code == "EDITOR_REJECTED":
        return "Editorial gate rejected this draft."
    if code in TRANSIENT_CODES:
        return "The provider is temporarily unavailable."
    return "Production stopped safely. Review the reported reason before continuing."
