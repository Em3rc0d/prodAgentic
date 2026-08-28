import hashlib

from core.grounding import GroundingAssessmentBuilder, GroundingPolicy
from core.semantic_matcher import SemanticMatcherBoundary
from models.claim_extractor import (
    ClaimExtractionOutput,
    ClaimExtractionReviewDecision,
    ClaimExtractionReviewSnapshot,
    claim_extraction_sha256,
)
from models.grounding import (
    ClaimProposal,
    ClaimType,
    EvidenceMatchProposal,
    EvidenceRef,
    EvidenceRelation,
    GroundingDecision,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.semantic_matcher import SemanticMatcherInput, SemanticMatcherOutput
from routes.claim_extractor import require_verified_claim_extraction


def source_packet():
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="CI evidence",
        strict_mode=True,
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #376 completed successfully.",
            )
        ],
    )


def reviewed_run(content: str, claims: list[ClaimProposal]):
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    extraction = ClaimExtractionOutput(
        extraction_id="extract-1",
        content_sha256=content_sha,
        extractor_version="extractor-v1",
        claims=claims,
    )
    review = ClaimExtractionReviewSnapshot(
        review_id="review-1",
        decision=ClaimExtractionReviewDecision.VERIFIED_COMPLETE,
        extraction_id=extraction.extraction_id,
        content_sha256=content_sha,
        extraction_sha256=claim_extraction_sha256(extraction),
    )
    return {
        "final_content": content,
        "claim_extraction": extraction.model_dump(mode="python"),
        "claim_extraction_review": review.model_dump(mode="python"),
    }


def test_reviewed_extraction_can_flow_to_deterministic_grounding_pass():
    content = "CI #376 completed successfully."
    claim = ClaimProposal(
        claim_id="c1",
        statement=content,
        claim_type=ClaimType.FACT,
        confidence=0.95,
        text_start=0,
        text_end=len(content),
    )
    run = reviewed_run(content, [claim])
    extraction = require_verified_claim_extraction(run)
    packet = source_packet()

    matcher_input = SemanticMatcherInput(
        packet_id=packet.packet_id,
        content_sha256=extraction.content_sha256,
        claims=extraction.claims,
    )
    matcher_output = SemanticMatcherOutput(
        match_id="match-1",
        packet_id=packet.packet_id,
        content_sha256=extraction.content_sha256,
        matcher_version="matcher-v1",
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
        packet,
        extraction_complete=True,
    )
    assessment = GroundingAssessmentBuilder.build(draft, packet)
    gate = GroundingPolicy.evaluate(assessment, packet)

    assert gate.decision == GroundingDecision.PASS


def test_empty_reviewed_extraction_still_blocks_under_strict_grounding():
    content = "CI #376 completed successfully."
    run = reviewed_run(content, [])
    extraction = require_verified_claim_extraction(run)
    packet = source_packet()

    matcher_input = SemanticMatcherInput(
        packet_id=packet.packet_id,
        content_sha256=extraction.content_sha256,
        claims=extraction.claims,
    )
    matcher_output = SemanticMatcherOutput(
        match_id="match-empty",
        packet_id=packet.packet_id,
        content_sha256=extraction.content_sha256,
        matcher_version="matcher-v1",
        evidence_matches=[],
    )
    draft = SemanticMatcherBoundary.to_grounding_draft(
        matcher_input,
        matcher_output,
        packet,
        extraction_complete=True,
    )
    assessment = GroundingAssessmentBuilder.build(draft, packet)
    gate = GroundingPolicy.evaluate(assessment, packet)

    assert gate.decision == GroundingDecision.BLOCK
    assert "strict grounding requires a completed non-empty claim assessment" in gate.reasons
