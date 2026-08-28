import hashlib
import json
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.grounding import ClaimProposal, ClaimType


class ClaimExtractorProviderCandidate(BaseModel):
    """Narrow, untrusted provider proposal for one claim.

    Provider does not own claim IDs, content identity, offsets, completeness, or
    Grounding state. `verbatim_span` must be copied exactly from final content.
    """

    model_config = ConfigDict(extra="forbid")

    verbatim_span: str = Field(min_length=1, max_length=4000)
    statement: str = Field(min_length=1, max_length=4000)
    claim_type: ClaimType
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("verbatim_span", "statement")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("claim text must not be blank")
        return value


class ClaimExtractorProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimExtractorProviderCandidate] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def reject_exact_duplicates(self):
        keys = [
            (item.verbatim_span, item.statement, item.claim_type.value)
            for item in self.claims
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("claim extractor provider response contains duplicate claim proposals")
        return self


class ClaimExtractionOutput(BaseModel):
    extraction_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    extractor_version: str
    claims: list[ClaimProposal] = Field(default_factory=list, max_length=100)
    requires_human_completeness_review: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("extraction_id", "extractor_version")
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
    def require_unique_claim_ids_and_spans(self):
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim extraction output claim IDs must be unique")
        return self


class ClaimExtractionReviewDecision(str, Enum):
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    REJECTED = "REJECTED"


class ClaimExtractionReviewRequest(BaseModel):
    decision: ClaimExtractionReviewDecision


class ClaimExtractionReviewSnapshot(BaseModel):
    review_id: str
    decision: ClaimExtractionReviewDecision
    extraction_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    extraction_sha256: str = Field(min_length=64, max_length=64)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("review_id", "extraction_id")
    @classmethod
    def require_non_blank(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("content_sha256", "extraction_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("SHA-256 values must be hexadecimal")
        return value


def claim_extraction_sha256(extraction: ClaimExtractionOutput) -> str:
    canonical = json.dumps(
        extraction.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
