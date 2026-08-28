import pytest
from pydantic import ValidationError

from core.grounding import GroundingAssessmentBuilder, GroundingPolicy
from models.grounding import (
    ClaimProposal,
    ClaimType,
    EvidenceMatchProposal,
    EvidenceRef,
    EvidenceRelation,
    GroundingDecision,
    GroundingEvaluationDraft,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)


_SHA = "a" * 64
_CONTENT_SHA = "b" * 64


def _packet(*evidence_ids: str) -> SourcePacket:
    ids = evidence_ids or ("ev-1",)
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Grounding builder evidence",
        evidence=[
            EvidenceRef(
                evidence_id=evidence_id,
                authority=SourceAuthority.SYSTEM_DERIVED,
                source_type=SourceType.CI_EVIDENCE,
                locator=f"evidence://{evidence_id}",
                content_sha256=_SHA,
            )
            for evidence_id in ids
        ],
    )


def _claim(
    claim_type: ClaimType = ClaimType.FACT,
    *,
    claim_id: str = "claim-1",
    statement: str = "Two tests failed.",
) -> ClaimProposal:
    return ClaimProposal(
        claim_id=claim_id,
        statement=statement,
        claim_type=claim_type,
        confidence=0.9,
        text_start=0,
        text_end=len(statement),
    )


def _match(
    relation: EvidenceRelation,
    *,
    claim_id: str = "claim-1",
    evidence_id: str = "ev-1",
    confidence: float = 0.8,
) -> EvidenceMatchProposal:
    return EvidenceMatchProposal(
        claim_id=claim_id,
        evidence_id=evidence_id,
        relation=relation,
        confidence=confidence,
        rationale="test relation",
    )


def _draft(
    *claims: ClaimProposal,
    matches: list[EvidenceMatchProposal] | None = None,
    extraction_complete: bool = True,
    packet_id: str = "packet-1",
) -> GroundingEvaluationDraft:
    return GroundingEvaluationDraft(
        draft_id="draft-1",
        packet_id=packet_id,
        content_sha256=_CONTENT_SHA,
        evaluator_version="proposal-evaluator-v1",
        extraction_complete=extraction_complete,
        claims=list(claims),
        evidence_matches=matches or [],
    )


def test_supported_fact_becomes_grounded_only_in_deterministic_builder():
    draft = _draft(
        _claim(ClaimType.FACT),
        matches=[_match(EvidenceRelation.SUPPORTS)],
    )

    assessment = GroundingAssessmentBuilder.build(draft, _packet())

    assert assessment.claims[0].grounding_status == GroundingStatus.GROUNDED
    assert assessment.claims[0].source_refs == ["ev-1"]
    assert assessment.evaluator_version.endswith("grounding-assessment-builder-v1")
    assert GroundingPolicy.evaluate(assessment, _packet()).decision == GroundingDecision.PASS


def test_supported_inference_becomes_supported_inference_and_remains_warning():
    draft = _draft(
        _claim(
            ClaimType.INFERENCE,
            statement="The tests represented an older lifecycle assumption.",
        ),
        matches=[_match(EvidenceRelation.SUPPORTS)],
    )

    assessment = GroundingAssessmentBuilder.build(draft, _packet())
    gate = GroundingPolicy.evaluate(assessment, _packet())

    assert assessment.claims[0].grounding_status == GroundingStatus.SUPPORTED_INFERENCE
    assert gate.decision == GroundingDecision.PASS
    assert gate.warning_claim_ids == ["claim-1"]


def test_contradiction_wins_over_support_instead_of_averaging_truth():
    draft = _draft(
        _claim(ClaimType.FACT, statement="All tests passed."),
        matches=[
            _match(EvidenceRelation.SUPPORTS, evidence_id="ev-1", confidence=0.7),
            _match(EvidenceRelation.CONTRADICTS, evidence_id="ev-2", confidence=0.95),
        ],
    )
    packet = _packet("ev-1", "ev-2")

    assessment = GroundingAssessmentBuilder.build(draft, packet)
    gate = GroundingPolicy.evaluate(assessment, packet)

    assert assessment.claims[0].grounding_status == GroundingStatus.CONTRADICTED
    assert assessment.claims[0].source_refs == ["ev-2"]
    assert gate.decision == GroundingDecision.BLOCK


def test_missing_support_is_insufficient_even_when_matcher_returns_insufficient_rows():
    draft = _draft(
        _claim(ClaimType.FACT, statement="Reliability improved by 73 percent."),
        matches=[_match(EvidenceRelation.INSUFFICIENT)],
    )

    assessment = GroundingAssessmentBuilder.build(draft, _packet())
    gate = GroundingPolicy.evaluate(assessment, _packet())

    assert assessment.claims[0].grounding_status == GroundingStatus.INSUFFICIENT_EVIDENCE
    assert assessment.claims[0].source_refs == []
    assert gate.decision == GroundingDecision.BLOCK


def test_unknown_support_reference_is_not_silently_dropped_and_policy_blocks_it():
    draft = _draft(
        _claim(ClaimType.FACT),
        matches=[_match(EvidenceRelation.SUPPORTS, evidence_id="ev-outside-packet")],
    )
    packet = _packet("ev-1")

    assessment = GroundingAssessmentBuilder.build(draft, packet)
    gate = GroundingPolicy.evaluate(assessment, packet)

    assert assessment.claims[0].grounding_status == GroundingStatus.GROUNDED
    assert assessment.claims[0].source_refs == ["ev-outside-packet"]
    assert gate.decision == GroundingDecision.BLOCK
    assert any("outside the source packet" in reason for reason in gate.reasons)


def test_opinion_cannot_borrow_factual_authority_from_support_proposal():
    draft = _draft(
        _claim(
            ClaimType.OPINION,
            statement="Fail-closed persistence is the safer product choice.",
        ),
        matches=[_match(EvidenceRelation.SUPPORTS)],
    )

    assessment = GroundingAssessmentBuilder.build(draft, _packet())
    gate = GroundingPolicy.evaluate(assessment, _packet())

    assert assessment.claims[0].grounding_status == GroundingStatus.OPINION
    assert assessment.claims[0].source_refs == []
    assert gate.decision == GroundingDecision.PASS


def test_incomplete_extraction_remains_incomplete_and_policy_blocks():
    draft = _draft(
        _claim(ClaimType.FACT),
        matches=[_match(EvidenceRelation.SUPPORTS)],
        extraction_complete=False,
    )

    assessment = GroundingAssessmentBuilder.build(draft, _packet())
    gate = GroundingPolicy.evaluate(assessment, _packet())

    assert assessment.extraction_complete is False
    assert gate.decision == GroundingDecision.BLOCK
    assert any("extraction is incomplete" in reason for reason in gate.reasons)


def test_builder_rejects_packet_identity_mismatch():
    with pytest.raises(ValueError, match="packet_id"):
        GroundingAssessmentBuilder.build(
            _draft(_claim(), packet_id="packet-other"),
            _packet(),
        )


def test_draft_rejects_match_for_claim_that_was_never_extracted():
    with pytest.raises(ValidationError, match="unknown claim_id"):
        _draft(
            _claim(),
            matches=[
                _match(
                    EvidenceRelation.SUPPORTS,
                    claim_id="claim-never-extracted",
                )
            ],
        )


def test_draft_rejects_duplicate_relation_for_same_claim_and_evidence():
    duplicate = _match(EvidenceRelation.SUPPORTS)
    with pytest.raises(ValidationError, match="duplicate evidence relation"):
        _draft(
            _claim(),
            matches=[duplicate, duplicate.model_copy()],
        )
