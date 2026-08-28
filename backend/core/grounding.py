from models.grounding import (
    ClaimType,
    GroundingAssessment,
    GroundingDecision,
    GroundingGateResult,
    GroundingStatus,
    SourcePacket,
)


class GroundingPolicy:
    """Deterministic approval precondition for factual trust.

    Models may propose classifications and evidence links, but this policy owns
    the final mechanical decision about whether the assessment is eligible to
    move toward human approval.
    """

    VERSION = "grounding-policy-v1"

    @classmethod
    def evaluate(
        cls,
        assessment: GroundingAssessment,
        source_packet: SourcePacket,
    ) -> GroundingGateResult:
        blocking_claim_ids: list[str] = []
        warning_claim_ids: list[str] = []
        reasons: list[str] = []

        def block(claim_id: str | None, reason: str):
            if claim_id and claim_id not in blocking_claim_ids:
                blocking_claim_ids.append(claim_id)
            reasons.append(reason)

        if assessment.packet_id != source_packet.packet_id:
            block(None, "assessment packet_id does not match source packet")

        if not assessment.extraction_complete:
            block(None, "claim extraction is incomplete")

        if source_packet.strict_mode and not assessment.claims:
            block(None, "strict grounding requires a completed non-empty claim assessment")

        evidence_ids = {item.evidence_id for item in source_packet.evidence}

        for claim in assessment.claims:
            unknown_refs = [ref for ref in claim.source_refs if ref not in evidence_ids]
            if unknown_refs:
                block(
                    claim.claim_id,
                    f"claim {claim.claim_id} references evidence outside the source packet: {', '.join(unknown_refs)}",
                )

            if claim.grounding_status == GroundingStatus.INSUFFICIENT_EVIDENCE:
                block(claim.claim_id, f"claim {claim.claim_id} has insufficient evidence")
                continue

            if claim.grounding_status == GroundingStatus.CONTRADICTED:
                block(claim.claim_id, f"claim {claim.claim_id} is contradicted by attached evidence")
                continue

            if claim.claim_type in {ClaimType.FACT, ClaimType.EXPERIENCE}:
                if claim.grounding_status != GroundingStatus.GROUNDED:
                    block(claim.claim_id, f"claim {claim.claim_id} must be GROUNDED")
                continue

            if claim.claim_type in {
                ClaimType.INFERENCE,
                ClaimType.ESTIMATE,
                ClaimType.PREDICTION,
            }:
                if claim.grounding_status != GroundingStatus.SUPPORTED_INFERENCE:
                    block(claim.claim_id, f"claim {claim.claim_id} must be SUPPORTED_INFERENCE")
                elif claim.claim_id not in warning_claim_ids:
                    warning_claim_ids.append(claim.claim_id)
                continue

            if claim.claim_type == ClaimType.OPINION:
                if claim.grounding_status != GroundingStatus.OPINION:
                    block(claim.claim_id, f"claim {claim.claim_id} must remain explicitly OPINION")

        decision = GroundingDecision.BLOCK if reasons else GroundingDecision.PASS
        return GroundingGateResult(
            policy_version=cls.VERSION,
            decision=decision,
            blocking_claim_ids=blocking_claim_ids,
            warning_claim_ids=warning_claim_ids,
            reasons=reasons,
        )
