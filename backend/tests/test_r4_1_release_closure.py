from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace

import pytest

from application.production.recovery import recovery_decision
from application.production.service import StructuredAgentCellService
from domain.planning.models import ContentEditorialState
from domain.production.evidence import (
    AcquisitionStatus,
    EvidenceBundleV1,
    EvidenceProvenanceV1,
    EvidenceSourceV1,
    verify_research_evidence,
)
from domain.production.failures import ProductionRecoveryAction
from domain.production.models import (
    ClaimCategory,
    ClaimConfidence,
    ClaimPublishability,
    ClaimV1,
    EvidenceSourceType,
    GenerationFailureV1,
    GenerationRunState,
    GenerationRunV1,
    ResearchPackV1,
    ResearchVerdict,
    canonical_sha256,
)


NOW = datetime(2026, 9, 16, 20, 0, tzinfo=timezone.utc)


def _source() -> EvidenceSourceV1:
    excerpt = "Bounded provider-grounded summary."
    return EvidenceSourceV1(
        evidence_id="evidence-1",
        locator="https://example.com/source",
        canonical_url="https://example.com/source",
        title="Bounded source",
        publisher_domain="example.com",
        source_type=EvidenceSourceType.WEB,
        retrieved_at=NOW,
        normalized_excerpt=excerpt,
        content_digest=hashlib.sha256(excerpt.encode()).hexdigest(),
        provider="google",
        provenance=EvidenceProvenanceV1(
            method="google_search_grounding",
            model="gemini-fixture",
            chunk_index=0,
            support_indices=(0,),
        ),
    )


def _bundle() -> EvidenceBundleV1:
    return EvidenceBundleV1(
        bundle_id="bundle-1",
        tenant_id="tenant-1",
        plan_id="plan-1",
        plan_digest="a" * 64,
        sources=(_source(),),
        acquisition_status=AcquisitionStatus.ACQUIRED,
        query_digest="b" * 64,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def _research(bundle: EvidenceBundleV1) -> ResearchPackV1:
    source = bundle.sources[0]
    return ResearchPackV1(
        research_id="research-1",
        plan_id=bundle.plan_id,
        verdict=ResearchVerdict.GO,
        claims=(
            ClaimV1(
                claim_id="claim-1",
                statement="A bounded factual statement.",
                category=ClaimCategory.FACTUAL,
                confidence=ClaimConfidence.MEDIUM,
                evidence_refs=(source.evidence_id,),
                publishability=ClaimPublishability.ALLOWED,
            ),
        ),
        evidence=(source.as_reference(),),
        evidence_bundle_ref=bundle.bundle_id,
        evidence_bundle_digest=canonical_sha256(bundle),
    )


def test_r4_1_evidence_authority_rejects_tampering_and_unbound_factual_claims():
    bundle = _bundle()
    research = _research(bundle)
    verify_research_evidence(research, bundle)

    tampered_ref = research.evidence[0].model_copy(update={"title": "Changed by model"})
    tampered = research.model_copy(update={"evidence": (tampered_ref,)})
    with pytest.raises(ValueError, match="changed acquired evidence metadata"):
        verify_research_evidence(tampered, bundle)

    unbound_claim = research.claims[0].model_copy(update={"evidence_refs": ()})
    unbound = research.model_copy(update={"claims": (unbound_claim,)})
    with pytest.raises(ValueError, match="lacks acquired evidence"):
        verify_research_evidence(unbound, bundle)


def test_r4_1_failed_recovery_distinguishes_retry_replan_and_resume():
    failed_item = SimpleNamespace(
        content_id="content-1",
        editorial_state=ContentEditorialState.FAILED,
        current_revision_id=None,
    )
    transient = SimpleNamespace(
        run_id="run-transient",
        state=GenerationRunState.FAILED,
        failure=GenerationFailureV1(
            code="MODEL_TIMEOUT",
            stage="research",
            retryable=True,
            recovery_action=ProductionRecoveryAction.RETRY_PRODUCTION,
            safe_message="Provider timed out.",
        ),
    )
    semantic = SimpleNamespace(
        run_id="run-semantic",
        state=GenerationRunState.FAILED,
        failure=GenerationFailureV1(
            code="RESEARCH_NO_GO",
            stage="research",
            retryable=False,
            recovery_action=ProductionRecoveryAction.REPLAN_CONTENT,
            safe_message="Reliable evidence was insufficient.",
        ),
    )
    saved_item = SimpleNamespace(
        content_id="content-1",
        editorial_state=ContentEditorialState.PRODUCING,
        current_revision_id="revision-1",
    )
    saved_run = SimpleNamespace(
        run_id="run-render",
        state=GenerationRunState.RENDERING,
        failure=None,
    )

    assert recovery_decision(failed_item, transient).action == ProductionRecoveryAction.RETRY_PRODUCTION
    assert recovery_decision(failed_item, semantic).action == ProductionRecoveryAction.REPLAN_CONTENT
    assert recovery_decision(saved_item, saved_run).action == ProductionRecoveryAction.RESUME_PIPELINE


@pytest.mark.asyncio
async def test_r4_1_diagnostics_failure_cannot_override_persisted_failed_run():
    class Repository:
        def __init__(self):
            self.saved = None

        async def update_run(self, run):
            self.saved = run

        async def list_agent_attempts(self, tenant_id, run_id):
            raise RuntimeError("diagnostics backend unavailable")

    repository = Repository()
    service = StructuredAgentCellService(
        repository=repository,
        research_agent=None,
        writer_agent=None,
        editor_agent=None,
    )
    run = GenerationRunV1(
        run_id="run-1",
        tenant_id="tenant-1",
        content_id="content-1",
        profile_id="profile-1",
        profile_version=1,
        profile_snapshot_digest="c" * 64,
        plan_id="plan-1",
        plan_digest="d" * 64,
        state=GenerationRunState.RESEARCHING,
        contract_versions=("GenerationRunV1@1",),
        started_at=NOW,
    )

    failed = await service._fail_run(
        run,
        "MODEL_TIMEOUT",
        "research",
        retryable=True,
    )

    assert repository.saved == failed
    assert failed.state == GenerationRunState.FAILED
    assert failed.failure is not None
    assert failed.failure.recovery_action == ProductionRecoveryAction.RETRY_PRODUCTION
    assert failed.completed_at is not None
