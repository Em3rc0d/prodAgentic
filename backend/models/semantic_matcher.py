from pydantic import BaseModel, Field, field_validator, model_validator

from models.grounding import ClaimProposal, EvidenceMatchProposal


class SemanticMatcherInput(BaseModel):
    packet_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    claims: list[ClaimProposal] = Field(default_factory=list)

    @field_validator("packet_id")
    @classmethod
    def require_packet_id(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("packet_id must not be blank")
        return value

    @field_validator("content_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        value = value.lower()
        if any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("content_sha256 must be hexadecimal")
        return value

    @model_validator(mode="after")
    def require_unique_claims(self):
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("semantic matcher input claim ids must be unique")
        return self


class SemanticMatcherProviderResponse(BaseModel):
    """Narrow untrusted provider payload.

    The model may propose claim/evidence relations only. Packet identity, content
    identity, matcher identity and authoritative Grounding state are all owned by
    server-side code outside this schema.
    """

    evidence_matches: list[EvidenceMatchProposal] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_relations(self):
        keys = [
            (match.claim_id, match.evidence_id, match.relation.value)
            for match in self.evidence_matches
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("semantic matcher provider response contains duplicate evidence relations")
        return self


class SemanticMatcherOutput(BaseModel):
    match_id: str
    packet_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    matcher_version: str
    evidence_matches: list[EvidenceMatchProposal] = Field(default_factory=list)

    @field_validator("match_id", "packet_id", "matcher_version")
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
    def reject_duplicate_relations(self):
        keys = [
            (match.claim_id, match.evidence_id, match.relation.value)
            for match in self.evidence_matches
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("semantic matcher output contains duplicate evidence relations")
        return self


class SemanticMatchDraftRequest(BaseModel):
    """Request a non-authoritative provider-generated Grounding draft."""

    packet_id: str
    claims: list[ClaimProposal] = Field(default_factory=list)
    extraction_complete: bool = True

    @field_validator("packet_id")
    @classmethod
    def require_packet_id(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("packet_id must not be blank")
        return value

    @model_validator(mode="after")
    def require_unique_claims(self):
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("semantic match request claim ids must be unique")
        return self
