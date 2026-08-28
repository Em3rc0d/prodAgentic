from models.grounding import (
    Claim,
    ClaimType,
    EvidenceRelation,
    GroundingAssessment,
    GroundingDecision,
    GroundingEvaluationDraft,
    GroundingGateResult,
    GroundingStatus,
    SourcePacket,
)


class GroundingAssessmentBuilder:
    """Convert non-authoritative semantic proposals into an assessment.

    Extractors and LLM evaluators may propose claims and evidence relations, but
    they never assign GroundingStatus directly. This builder derives those
    states mechanically and conservatively.
    """

    VERSION = "grounding-assessment-builder-v1"

    @classmethod
    def build(
        cls,
        draft: GroundingEvaluationDraft,
        source_packet: SourcePacket,
    ) -> GroundingAssessment:
        if draft.packet_id != source_packet.packet_id:
            raise ValueError("grounding draft packet_id does not match source packet")

        matches_by_claim = {claim.claim_id: [] for claim in draft.claims}
        for match in draft.evidence_matches:
            matches_by_claim[match.claim_id].append(match)

        claims: list[Claim] = []
        for proposal in draft.claims:
            matches = matches_by_claim[proposal.claim_id]
            contradictions = [
                match for match in matches if match.relation == EvidenceRelation.CONTRADICTS
            ]
            supports = [
                match for match in matches if match.relation == EvidenceRelation.SUPPORTS
            ]

            if proposal.claim_type == ClaimType.OPINION:
                status = GroundingStatus.OPINION
                source_refs: list[str] = []
                rationale = "Opinion classification remains explicit and does not borrow factual authority from evidence."
                confidence = proposal.confidence
            elif contradictions:
                status = GroundingStatus.CONTRADICTED
                source_refs = sorted({match.evidence_id for match in contradictions})
                rationale = "At least one proposed evidence relation contradicts this claim."
                confidence = min(
                    proposal.confidence,
                    max(match.confidence for match in contradictions),
                )
            elif supports:
                if proposal.claim_type in {ClaimType.FACT, ClaimType.EXPERIENCE}:
                    status = GroundingStatus.GROUNDED
                else:
                    status = GroundingStatus.SUPPORTED_INFERENCE
                source_refs = sorted({match.evidence_id for match in supports})
                rationale = "At least one proposed evidence relation supports this claim and no contradiction was proposed."
                confidence = min(
                    proposal.confidence,
                    max(match.confidence for match in supports),
                )
            else:
                status = GroundingStatus.INSUFFICIENT_EVIDENCE
                source_refs = []
                rationale = "No supporting evidence relation was proposed for this claim."
                confidence = proposal.confidence

            claims.append(
                Claim(
                    claim_id=proposal.claim_id,
                    statement=proposal.statement,
                    claim_type=proposal.claim_type,
                    grounding_status=status,
                    source_refs=source_refs,
                    rationale=rationale,
                    confidence=confidence,
                )
            )

        return GroundingAssessment(
            assessment_id=f"assessment:{draft.draft_id}",
            packet_id=draft.packet_id,
            content_sha256=draft.content_sha256,
            evaluator_version=f"{draft.evaluator_version}+{cls.VERSION}",
            extraction_complete=draft.extraction_complete,
            claims=claims,
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
