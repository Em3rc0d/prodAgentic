import pytest
from pydantic import ValidationError

from core.grounding import GroundingPolicy
from models.grounding import (
    Claim,
    ClaimType,
    EvidenceRef,
    GroundingAssessment,
    GroundingDecision,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)


_SHA = "a" * 64


def _evidence(evidence_id: str = "ev-1") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        authority=SourceAuthority.SYSTEM_DERIVED,
        source_type=SourceType.CI_EVIDENCE,
        locator="github-actions://run/33127455899",
        excerpt="150 passed, 2 failed",
        content_sha256=_SHA,
    )


def _packet(*evidence: EvidenceRef, strict_mode: bool = True) -> SourcePacket:
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="CI hardening evidence",
        strict_mode=strict_mode,
        evidence=list(evidence or (_evidence(),)),
    )


def _assessment(*claims: Claim, extraction_complete: bool = True) -> GroundingAssessment:
    return GroundingAssessment(
        assessment_id="assessment-1",
        packet_id="packet-1",
        content_sha256="b" * 64,
        evaluator_version="test-evaluator-v1",
        extraction_complete=extraction_complete,
        claims=list(claims),
    )


def test_grounded_fact_passes():
    claim = Claim(
        claim_id="claim-1",
        statement="Two tests failed.",
        claim_type=ClaimType.FACT,
        grounding_status=GroundingStatus.GROUNDED,
        source_refs=["ev-1"],
        confidence=1.0,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.PASS
    assert result.blocking_claim_ids == []
    assert result.reasons == []


def test_unsupported_fact_blocks():
    claim = Claim(
        claim_id="claim-1",
        statement="Reliability improved by 73 percent.",
        claim_type=ClaimType.FACT,
        grounding_status=GroundingStatus.INSUFFICIENT_EVIDENCE,
        source_refs=[],
        confidence=0.4,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.BLOCK
    assert result.blocking_claim_ids == ["claim-1"]
    assert any("insufficient evidence" in reason for reason in result.reasons)


def test_contradicted_claim_hard_blocks():
    claim = Claim(
        claim_id="claim-1",
        statement="All tests passed.",
        claim_type=ClaimType.FACT,
        grounding_status=GroundingStatus.CONTRADICTED,
        source_refs=["ev-1"],
        confidence=0.99,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.BLOCK
    assert result.blocking_claim_ids == ["claim-1"]
    assert any("contradicted" in reason for reason in result.reasons)


def test_supported_inference_passes_but_is_visible_for_human_review():
    claim = Claim(
        claim_id="claim-1",
        statement="The tests still represented the older lifecycle assumption.",
        claim_type=ClaimType.INFERENCE,
        grounding_status=GroundingStatus.SUPPORTED_INFERENCE,
        source_refs=["ev-1"],
        confidence=0.8,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.PASS
    assert result.warning_claim_ids == ["claim-1"]


def test_incomplete_claim_extraction_blocks_even_when_known_claims_are_grounded():
    claim = Claim(
        claim_id="claim-1",
        statement="Two tests failed.",
        claim_type=ClaimType.FACT,
        grounding_status=GroundingStatus.GROUNDED,
        source_refs=["ev-1"],
        confidence=1.0,
    )

    result = GroundingPolicy.evaluate(
        _assessment(claim, extraction_complete=False),
        _packet(),
    )

    assert result.decision == GroundingDecision.BLOCK
    assert any("extraction is incomplete" in reason for reason in result.reasons)


def test_unknown_evidence_reference_blocks():
    claim = Claim(
        claim_id="claim-1",
        statement="Two tests failed.",
        claim_type=ClaimType.FACT,
        grounding_status=GroundingStatus.GROUNDED,
        source_refs=["ev-outside-packet"],
        confidence=1.0,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.BLOCK
    assert result.blocking_claim_ids == ["claim-1"]
    assert any("outside the source packet" in reason for reason in result.reasons)


def test_strict_mode_rejects_empty_claim_assessment():
    result = GroundingPolicy.evaluate(_assessment(), _packet(strict_mode=True))

    assert result.decision == GroundingDecision.BLOCK
    assert any("non-empty claim assessment" in reason for reason in result.reasons)


def test_grounded_claim_requires_source_reference():
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim-1",
            statement="Two tests failed.",
            claim_type=ClaimType.FACT,
            grounding_status=GroundingStatus.GROUNDED,
            source_refs=[],
            confidence=1.0,
        )


def test_fact_cannot_be_downgraded_to_supported_inference():
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim-1",
            statement="Two tests failed.",
            claim_type=ClaimType.FACT,
            grounding_status=GroundingStatus.SUPPORTED_INFERENCE,
            source_refs=["ev-1"],
            confidence=1.0,
        )


def test_opinion_remains_explicitly_opinion_without_fake_evidence_requirement():
    claim = Claim(
        claim_id="claim-1",
        statement="Fail-closed persistence is the safer product choice.",
        claim_type=ClaimType.OPINION,
        grounding_status=GroundingStatus.OPINION,
        source_refs=[],
        confidence=1.0,
    )

    result = GroundingPolicy.evaluate(_assessment(claim), _packet())

    assert result.decision == GroundingDecision.PASS
