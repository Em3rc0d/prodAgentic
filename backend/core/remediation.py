import hashlib
import json

from core.grounding import GroundingPolicy, source_packet_sha256
from models.grounding import GroundingAssessment, GroundingStatus, SourcePacket
from models.remediation import (
    GroundingRemediationDraft,
    RemediationAction,
    RemediationGateResult,
)


def _sha256_json(value) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def grounding_assessment_sha256(assessment: GroundingAssessment) -> str:
    return _sha256_json(assessment.model_dump(mode="json"))


class RemediationPolicy:
    """Validate remediation proposals without granting factual authority.

    This policy only answers whether a proposal set is structurally safe to use
    as a rewrite/removal plan. It never turns a blocked claim into GROUNDED.
    Any content change must be extracted, matched, gated and human-reviewed again.
    """

    VERSION = "grounding-remediation-policy-v1"

    @classmethod
    def evaluate(
        cls,
        draft: GroundingRemediationDraft,
        assessment: GroundingAssessment,
        source_packet: SourcePacket,
    ) -> RemediationGateResult:
        reasons: list[str] = []
        proposed_actions = {proposal.claim_id: proposal.action for proposal in draft.proposals}

        def reject(reason: str):
            reasons.append(reason)

        current_packet_sha = source_packet_sha256(source_packet)
        current_assessment_sha = grounding_assessment_sha256(assessment)

        if draft.packet_id != source_packet.packet_id or assessment.packet_id != source_packet.packet_id:
            reject("remediation packet identity does not match current Grounding material")
        if draft.content_sha256 != assessment.content_sha256:
            reject("remediation is stale relative to the assessed content")
        if draft.source_packet_sha256 != current_packet_sha:
            reject("remediation is stale relative to the current source packet")
        if draft.assessment_id != assessment.assessment_id:
            reject("remediation assessment_id does not match the current assessment")
        if draft.assessment_sha256 != current_assessment_sha:
            reject("remediation is stale relative to the current assessment")

        gate = GroundingPolicy.evaluate(assessment, source_packet)
        blocking_claim_ids = list(gate.blocking_claim_ids)

        if not assessment.extraction_complete:
            reject("incomplete extraction must be reevaluated; claim remediation cannot repair it")

        if gate.decision.value == "PASS":
            if draft.proposals:
                reject("a PASS assessment must not be rewritten through the blocked-claim remediation path")
            return RemediationGateResult(
                policy_version=cls.VERSION,
                valid=not reasons,
                blocking_claim_ids=[],
                proposed_actions=proposed_actions,
                reasons=reasons,
                requires_regrounding=False,
            )

        if not blocking_claim_ids:
            reject("Grounding is blocked by structural evidence/extraction state, not remediable claim text")

        proposal_ids = {proposal.claim_id for proposal in draft.proposals}
        blocker_ids = set(blocking_claim_ids)
        missing = sorted(blocker_ids - proposal_ids)
        extra = sorted(proposal_ids - blocker_ids)
        if missing:
            reject(f"missing remediation proposals for blocking claims: {', '.join(missing)}")
        if extra:
            reject(f"remediation includes non-blocking or unknown claims: {', '.join(extra)}")

        claims_by_id = {claim.claim_id: claim for claim in assessment.claims}
        evidence_ids = {evidence.evidence_id for evidence in source_packet.evidence}

        for proposal in draft.proposals:
            claim = claims_by_id.get(proposal.claim_id)
            if claim is None:
                reject(f"remediation references unknown claim {proposal.claim_id}")
                continue

            if proposal.action == RemediationAction.KEEP:
                reject(f"blocking claim {claim.claim_id} cannot be KEEP")
                continue

            if claim.grounding_status == GroundingStatus.CONTRADICTED:
                if proposal.action != RemediationAction.REMOVE:
                    reject(f"contradicted claim {claim.claim_id} must be REMOVE")
                continue

            if claim.grounding_status == GroundingStatus.INSUFFICIENT_EVIDENCE:
                if proposal.action == RemediationAction.SOFTEN:
                    if proposal.proposed_statement == claim.statement:
                        reject(f"SOFTEN for claim {claim.claim_id} must actually change the wording")
                    unknown_refs = [ref for ref in proposal.source_refs if ref not in evidence_ids]
                    if unknown_refs:
                        reject(
                            f"SOFTEN for claim {claim.claim_id} references evidence outside the source packet: "
                            + ", ".join(unknown_refs)
                        )
                elif proposal.action != RemediationAction.REMOVE:
                    reject(f"insufficient claim {claim.claim_id} must be SOFTEN or REMOVE")
                continue

            # Any other mechanically blocked state is treated conservatively.
            if proposal.action != RemediationAction.REMOVE:
                reject(f"blocked claim {claim.claim_id} may only be REMOVE under the current policy")

        return RemediationGateResult(
            policy_version=cls.VERSION,
            valid=not reasons,
            blocking_claim_ids=blocking_claim_ids,
            proposed_actions=proposed_actions,
            reasons=reasons,
            # Applying either SOFTEN or REMOVE changes the content revision.
            # A fresh full Grounding lifecycle is always required afterward.
            requires_regrounding=bool(draft.proposals),
        )
