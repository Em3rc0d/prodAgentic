import pytest
from pydantic import ValidationError

from core.grounding import GroundingAssessmentBuilder
from core.semantic_matcher import SemanticMatcherBoundary
from models.grounding import (
    ClaimProposal,
    ClaimType,
    EvidenceMatchProposal,
    EvidenceRef,
    EvidenceRelation,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.semantic_matcher import SemanticMatcherInput, SemanticMatcherOutput


CONTENT_SHA = "a" * 64


def packet():
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Evidence",
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #338 completed successfully for the exact candidate SHA.",
            )
        ],
    )


def claim():
    return ClaimProposal(
        claim_id="c1",
        statement="CI #338 completed successfully.",
        claim_type=ClaimType.FACT,
        confidence=0.95,
    )


def test_semantic_matcher_relations_flow_through_deterministic_assessment_builder():
    source_packet = packet()
    matcher_input = SemanticMatcherInput(
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        claims=[claim()],
    )
    matcher_output = SemanticMatcherOutput(
        match_id="m1",
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        matcher_version="fake-semantic-v1",
        evidence_matches=[
            EvidenceMatchProposal(
                claim_id="c1",
                evidence_id="e1",
                relation=EvidenceRelation.SUPPORTS,
                confidence=0.9,
            )
        ],
    )

    draft = SemanticMatcherBoundary.to_grounding_draft(
        matcher_input,
        matcher_output,
        source_packet,
        extraction_complete=True,
    )
    assessment = GroundingAssessmentBuilder.build(draft, source_packet)

    assert draft.claims == matcher_input.claims
    assert assessment.claims[0].grounding_status == GroundingStatus.GROUNDED
    assert "semantic-matcher-boundary-v1" in assessment.evaluator_version


def test_semantic_matcher_cannot_return_relation_for_unextracted_claim():
    source_packet = packet()
    matcher_input = SemanticMatcherInput(
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        claims=[claim()],
    )
    matcher_output = SemanticMatcherOutput(
        match_id="m1",
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        matcher_version="fake-semantic-v1",
        evidence_matches=[
            EvidenceMatchProposal(
                claim_id="invented-claim",
                evidence_id="e1",
                relation=EvidenceRelation.SUPPORTS,
                confidence=0.9,
            )
        ],
    )

    with pytest.raises(ValueError, match="unknown claim"):
        SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            source_packet,
            extraction_complete=True,
        )


def test_semantic_matcher_cannot_return_relation_for_unknown_evidence():
    source_packet = packet()
    matcher_input = SemanticMatcherInput(
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        claims=[claim()],
    )
    matcher_output = SemanticMatcherOutput(
        match_id="m1",
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        matcher_version="fake-semantic-v1",
        evidence_matches=[
            EvidenceMatchProposal(
                claim_id="c1",
                evidence_id="invented-evidence",
                relation=EvidenceRelation.SUPPORTS,
                confidence=0.9,
            )
        ],
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            source_packet,
            extraction_complete=True,
        )


def test_semantic_matcher_output_cannot_switch_content_revision():
    source_packet = packet()
    matcher_input = SemanticMatcherInput(
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        claims=[claim()],
    )
    matcher_output = SemanticMatcherOutput(
        match_id="m1",
        packet_id="packet-1",
        content_sha256="b" * 64,
        matcher_version="fake-semantic-v1",
    )

    with pytest.raises(ValueError, match="different content"):
        SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            source_packet,
            extraction_complete=True,
        )


def test_semantic_matcher_output_rejects_duplicate_relations():
    relation = EvidenceMatchProposal(
        claim_id="c1",
        evidence_id="e1",
        relation=EvidenceRelation.SUPPORTS,
        confidence=0.9,
    )

    with pytest.raises(ValidationError, match="duplicate evidence relations"):
        SemanticMatcherOutput(
            match_id="m1",
            packet_id="packet-1",
            content_sha256=CONTENT_SHA,
            matcher_version="fake-semantic-v1",
            evidence_matches=[relation, relation],
        )
