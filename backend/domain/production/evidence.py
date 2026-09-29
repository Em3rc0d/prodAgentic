"""Provider-independent, bounded external evidence authority."""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from domain.planning.models import ContentPlanV1
from domain.profiles.models import ProfileVersion
from domain.production.models import FrozenModel, EvidenceSourceType, EvidenceTrustLevel, EvidenceRefV1, canonical_sha256


class AcquisitionStatus(str, Enum):
    ACQUIRED = "ACQUIRED"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceProvenanceV1(FrozenModel):
    method: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=240)
    excerpt_kind: Literal["grounded_summary", "source_excerpt"] = "grounded_summary"
    # These are provider attribution indices, not model-authored citations.
    chunk_index: int = Field(ge=0, le=255)
    support_indices: tuple[int, ...] = Field(min_length=1, max_length=32)
    publisher_verified: bool = False


class EvidenceSourceV1(FrozenModel):
    schema_version: Literal[1] = 1
    evidence_id: str = Field(min_length=1, max_length=128)
    locator: str = Field(min_length=1, max_length=2000)
    canonical_url: str | None = Field(default=None, max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    publisher_domain: str = Field(min_length=1, max_length=253)
    source_type: EvidenceSourceType = EvidenceSourceType.WEB
    retrieved_at: datetime
    normalized_excerpt: str = Field(min_length=1, max_length=2000)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str = Field(min_length=1, max_length=120)
    provenance: EvidenceProvenanceV1

    @model_validator(mode="after")
    def validate_source(self):
        for value in (self.locator, self.canonical_url):
            if value is None:
                continue
            parts = urlsplit(value)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise ValueError("Evidence requires a credential-free HTTPS locator")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("Evidence retrieval time requires a timezone")
        if hashlib.sha256(self.normalized_excerpt.encode()).hexdigest() != self.content_digest:
            raise ValueError("Evidence excerpt digest mismatch")
        return self

    def as_reference(self) -> EvidenceRefV1:
        return EvidenceRefV1(
            evidence_id=self.evidence_id, source_type=self.source_type, title=self.title,
            locator=self.locator, observed_at=self.retrieved_at,
            trusted_level=EvidenceTrustLevel.SECONDARY,
            notes="Provider-grounded summary; not a verbatim page excerpt or independent verification.",
        )


class EvidenceBundleV1(FrozenModel):
    schema_version: Literal[1] = 1
    bundle_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    plan_id: str = Field(min_length=1, max_length=128)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: tuple[EvidenceSourceV1, ...] = Field(default=(), max_length=12)
    acquisition_status: AcquisitionStatus
    query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_bundle(self):
        if len({s.evidence_id for s in self.sources}) != len(self.sources):
            raise ValueError("Duplicate evidence identity")
        if (self.acquisition_status == AcquisitionStatus.ACQUIRED) != bool(self.sources):
            raise ValueError("Acquisition status contradicts bounded evidence")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None or self.expires_at <= self.created_at:
            raise ValueError("Invalid evidence validity interval")
        return self


class EvidenceAcquisitionPort(Protocol):
    async def acquire(self, *, tenant_id: str, run_id: str, plan: ContentPlanV1,
                      profile: ProfileVersion) -> EvidenceBundleV1: ...


def verify_research_evidence(research, bundle: EvidenceBundleV1) -> None:
    from domain.production.models import ClaimCategory, ClaimPublishability
    if (research.plan_id != bundle.plan_id or research.evidence_bundle_ref != bundle.bundle_id
            or research.evidence_bundle_digest != canonical_sha256(bundle)):
        raise ValueError("Research/evidence authority mismatch")
    sources = {s.evidence_id: s for s in bundle.sources}
    for ref in research.evidence:
        source = sources.get(ref.evidence_id)
        if source is None or ref != source.as_reference():
            raise ValueError("Research changed acquired evidence metadata")
    for claim in research.claims:
        if claim.category == ClaimCategory.FACTUAL and claim.publishability != ClaimPublishability.FORBIDDEN:
            if not claim.evidence_refs or not set(claim.evidence_refs).issubset(sources):
                raise ValueError("Publishable factual claim lacks acquired evidence")


async def load_run_evidence(repository, tenant_id, run, research) -> EvidenceBundleV1 | None:
    """Used again at QA/approval; validates persisted predecessors, not only DTOs."""
    required = "EvidenceBundleV1@1" in run.contract_versions
    if run.research_pack_ref != research.research_id:
        raise ValueError("Research identity mismatch")
    if run.evidence_bundle_ref is None:
        if required or research.evidence_bundle_ref is not None:
            raise ValueError("Evidence authority is missing")
        return None  # Historical R4/demo lineage, never relabelled R4.1.
    record = await repository.get_artifact(tenant_id, run.evidence_bundle_ref)
    if record is None or record.get("artifact_type") != "EvidenceBundleV1":
        raise ValueError("Evidence artifact is unavailable")
    bundle = EvidenceBundleV1.model_validate(record["payload"])
    digest = canonical_sha256(bundle)
    if (record.get("digest") != digest or run.evidence_bundle_digest != digest
            or bundle.tenant_id != tenant_id or bundle.plan_id != run.plan_id
            or bundle.plan_digest != run.plan_digest or bundle.bundle_id != run.evidence_bundle_ref):
        raise ValueError("Evidence predecessor digest mismatch")
    owner = await repository.get_run(tenant_id, record.get("run_id"))
    if (owner is None or owner.content_id != run.content_id or owner.plan_digest != run.plan_digest
            or owner.profile_snapshot_digest != run.profile_snapshot_digest
            or owner.evidence_bundle_ref != bundle.bundle_id or owner.evidence_bundle_digest != digest):
        raise ValueError("Evidence owner lineage mismatch")
    research_record = await repository.get_artifact(tenant_id, research.research_id)
    research_owner = await repository.get_run(tenant_id, research_record.get("run_id")) if research_record else None
    if (research_record is None or research_record.get("artifact_type") != "ResearchPackV1"
            or research_record.get("digest") != canonical_sha256(research)
            or research_owner is None or research_owner.content_id != run.content_id
            or research_owner.plan_digest != run.plan_digest
            or research_owner.profile_snapshot_digest != run.profile_snapshot_digest
            or research_owner.research_pack_ref != research.research_id
            or research_owner.evidence_bundle_ref != bundle.bundle_id):
        raise ValueError("Research owner lineage mismatch")
    verify_research_evidence(research, bundle)
    return bundle
