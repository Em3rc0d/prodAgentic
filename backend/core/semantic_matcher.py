from typing import Protocol

from models.grounding import GroundingEvaluationDraft, SourcePacket
from models.semantic_matcher import SemanticMatcherInput, SemanticMatcherOutput


class SemanticMatcherAdapter(Protocol):
    """Provider boundary for non-authoritative semantic evidence matching."""

    async def match(
        self,
        matcher_input: SemanticMatcherInput,
        source_packet: SourcePacket,
    ) -> SemanticMatcherOutput:
        ...


class SemanticMatcherBoundary:
    """Validate matcher identity/provenance before creating a Grounding draft.

    The matcher is allowed to propose evidence relations only. Claims come from
    the extractor input unchanged, and GroundingStatus remains owned by the
    deterministic GroundingAssessmentBuilder.
    """

    VERSION = "semantic-matcher-boundary-v1"

    @classmethod
    def to_grounding_draft(
        cls,
        matcher_input: SemanticMatcherInput,
        matcher_output: SemanticMatcherOutput,
        source_packet: SourcePacket,
        *,
        extraction_complete: bool,
    ) -> GroundingEvaluationDraft:
        if matcher_input.packet_id != source_packet.packet_id:
            raise ValueError("semantic matcher input packet_id does not match source packet")
        if matcher_output.packet_id != source_packet.packet_id:
            raise ValueError("semantic matcher output packet_id does not match source packet")
        if matcher_output.content_sha256 != matcher_input.content_sha256:
            raise ValueError("semantic matcher output is stale or bound to different content")

        known_claims = {claim.claim_id for claim in matcher_input.claims}
        known_evidence = {item.evidence_id for item in source_packet.evidence}
        for match in matcher_output.evidence_matches:
            if match.claim_id not in known_claims:
                raise ValueError(f"semantic matcher returned relation for unknown claim {match.claim_id}")
            if match.evidence_id not in known_evidence:
                raise ValueError(
                    f"semantic matcher returned relation for unknown evidence {match.evidence_id}"
                )

        return GroundingEvaluationDraft(
            draft_id=f"semantic:{matcher_output.match_id}",
            packet_id=source_packet.packet_id,
            content_sha256=matcher_input.content_sha256,
            evaluator_version=(
                f"{matcher_output.matcher_version}+{cls.VERSION}"
            ),
            extraction_complete=extraction_complete,
            # Critical authority boundary: the matcher cannot replace or mutate
            # extractor claims. The exact input claims are forwarded.
            claims=matcher_input.claims,
            evidence_matches=matcher_output.evidence_matches,
        )
