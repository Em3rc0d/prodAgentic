import pytest
from pydantic import ValidationError

from core.grounding import FactualEnvelopeBuilder
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourceType,
)


def evidence(evidence_id: str = "e1", excerpt: str = "Observed release evidence") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        authority=SourceAuthority.SOURCE_SNAPSHOT,
        source_type=SourceType.DOCUMENT_EXCERPT,
        excerpt=excerpt,
    )


def test_raw_evidence_excerpt_is_not_promoted_into_allowed_facts():
    packet = SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Evidence only",
        evidence=[evidence(excerpt="Revenue increased 900 percent")],
    )

    envelope = FactualEnvelopeBuilder.build(packet)
    rendered = FactualEnvelopeBuilder.render_for_agent(envelope)

    assert envelope.allowed_facts == []
    assert envelope.allowed_inferences == []
    assert "Revenue increased 900 percent" not in rendered
    assert "ALLOWED FACTS\n- NONE" in rendered


def test_explicit_allowed_statement_preserves_evidence_provenance():
    packet = SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Release evidence",
        evidence=[evidence()],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-1",
                statement="The release gate completed successfully.",
                source_refs=["e1"],
            )
        ],
        prohibited_claims=["Do not claim customer impact without customer evidence."],
    )

    envelope = FactualEnvelopeBuilder.build(packet)
    rendered = FactualEnvelopeBuilder.render_for_agent(envelope)

    assert envelope.allowed_facts[0].source_refs == ["e1"]
    assert "[fact-1; evidence=e1] The release gate completed successfully." in rendered
    assert "Do not claim customer impact without customer evidence." in rendered


def test_source_packet_rejects_allowed_statement_with_unknown_evidence_ref():
    with pytest.raises(ValidationError, match="references evidence outside the source packet"):
        SourcePacket(
            packet_id="packet-1",
            workspace_id="workspace-1",
            title="Broken provenance",
            evidence=[evidence("e1")],
            allowed_facts=[
                EvidenceBoundStatement(
                    statement_id="fact-1",
                    statement="Unsupported promotion",
                    source_refs=["missing-evidence"],
                )
            ],
        )


def test_factual_envelope_digest_changes_when_source_packet_changes():
    packet_a = SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Packet",
        evidence=[evidence(excerpt="A")],
    )
    packet_b = SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Packet",
        evidence=[evidence(excerpt="B")],
        created_at=packet_a.created_at,
    )

    envelope_a = FactualEnvelopeBuilder.build(packet_a)
    envelope_b = FactualEnvelopeBuilder.build(packet_b)

    assert envelope_a.source_packet_sha256 != envelope_b.source_packet_sha256
