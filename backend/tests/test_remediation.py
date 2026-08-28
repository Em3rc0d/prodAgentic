from core.grounding import source_packet_sha256
from core.remediation import RemediationPolicy, grounding_assessment_sha256
from models.grounding import (
    Claim,
    ClaimType,
    EvidenceRef,
    GroundingAssessment,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.remediation import (
    ClaimRemediationProposal,
    GroundingRemediationDraft,
    RemediationAction,
)


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


def assessment(status: GroundingStatus, *, extraction_complete: bool = True):
    source_refs = ["e1"] if status == GroundingStatus.CONTRADICTED else []
    return GroundingAssessment(
        assessment_id="assessment-1",
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        evaluator_version="test-v1",
        extraction_complete=extraction_complete,
        claims=[
            Claim(
                claim_id="c1",
                statement="The release improved customer trust by 40%.",
                claim_type=ClaimType.FACT,
                grounding_status=status,
                source_refs=source_refs,
                confidence=0.9,
            )
        ],
    )


def draft(source_packet, current_assessment, proposal):
    return GroundingRemediationDraft(
        remediation_id="remediation-1",
        packet_id=source_packet.packet_id,
        content_sha256=current_assessment.content_sha256,
        source_packet_sha256=source_packet_sha256(source_packet),
        assessment_id=current_assessment.assessment_id,
        assessment_sha256=grounding_assessment_sha256(current_assessment),
        remediator_version="test-remediator-v1",
        proposals=[proposal],
    )


def test_insufficient_claim_can_be_softened_but_never_becomes_grounded_by_remediation():
    source_packet = packet()
    current = assessment(GroundingStatus.INSUFFICIENT_EVIDENCE)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.SOFTEN,
        proposed_statement="The exact candidate passed CI #338.",
        proposed_claim_type=ClaimType.FACT,
        source_refs=["e1"],
        rationale="Remove unsupported customer-impact language and retain only evidenced CI state.",
        confidence=0.9,
    )

    result = RemediationPolicy.evaluate(draft(source_packet, current, proposal), current, source_packet)

    assert result.valid is True
    assert result.proposed_actions == {"c1": RemediationAction.SOFTEN}
    assert result.requires_regrounding is True
    assert current.claims[0].grounding_status == GroundingStatus.INSUFFICIENT_EVIDENCE


def test_blocked_claim_cannot_be_kept():
    source_packet = packet()
    current = assessment(GroundingStatus.INSUFFICIENT_EVIDENCE)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.KEEP,
        confidence=0.8,
    )

    result = RemediationPolicy.evaluate(draft(source_packet, current, proposal), current, source_packet)

    assert result.valid is False
    assert any("cannot be KEEP" in reason for reason in result.reasons)


def test_contradicted_claim_must_be_removed_not_softened():
    source_packet = packet()
    current = assessment(GroundingStatus.CONTRADICTED)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.SOFTEN,
        proposed_statement="The release may have improved customer trust.",
        proposed_claim_type=ClaimType.INFERENCE,
        source_refs=["e1"],
        confidence=0.4,
    )

    result = RemediationPolicy.evaluate(draft(source_packet, current, proposal), current, source_packet)

    assert result.valid is False
    assert any("must be REMOVE" in reason for reason in result.reasons)


def test_contradicted_claim_remove_is_valid_but_requires_fresh_grounding_revision():
    source_packet = packet()
    current = assessment(GroundingStatus.CONTRADICTED)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.REMOVE,
        rationale="Evidence contradicts the claim.",
        confidence=0.99,
    )

    result = RemediationPolicy.evaluate(draft(source_packet, current, proposal), current, source_packet)

    assert result.valid is True
    assert result.requires_regrounding is True


def test_stale_remediation_assessment_digest_is_rejected():
    source_packet = packet()
    current = assessment(GroundingStatus.INSUFFICIENT_EVIDENCE)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.REMOVE,
        confidence=0.9,
    )
    remediation = draft(source_packet, current, proposal)
    remediation.assessment_sha256 = "b" * 64

    result = RemediationPolicy.evaluate(remediation, current, source_packet)

    assert result.valid is False
    assert any("stale relative to the current assessment" in reason for reason in result.reasons)


def test_incomplete_extraction_cannot_be_repaired_by_claim_rewrite():
    source_packet = packet()
    current = assessment(GroundingStatus.INSUFFICIENT_EVIDENCE, extraction_complete=False)
    proposal = ClaimRemediationProposal(
        claim_id="c1",
        action=RemediationAction.REMOVE,
        confidence=0.9,
    )

    result = RemediationPolicy.evaluate(draft(source_packet, current, proposal), current, source_packet)

    assert result.valid is False
    assert any("incomplete extraction" in reason for reason in result.reasons)
