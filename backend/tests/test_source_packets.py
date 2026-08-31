from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import routes.source_packets as source_packet_routes
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourcePacketCreateRequest,
    SourceType,
)
from models.source_packet import QuickSourcePacketRequest


def request_for_workspace(workspace_id: str):
    settings = SimpleNamespace(app_workspace_id=workspace_id)
    container = SimpleNamespace(settings=settings)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


def source_request(**extra):
    return SourcePacketCreateRequest(
        title="Release evidence",
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.PASTED_TEXT,
                excerpt="The build passed all release gates.",
            )
        ],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-1",
                statement="The build passed all release gates.",
                source_refs=["e1"],
            )
        ],
        **extra,
    )


@pytest.mark.asyncio
async def test_create_source_packet_uses_server_workspace_and_server_packet_id(monkeypatch):
    captured = {}

    class FakeRepository:
        def __init__(self, db):
            captured["db"] = db

        async def create(self, packet):
            captured["packet"] = packet
            return packet

    fake_db = object()
    monkeypatch.setattr(source_packet_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(source_packet_routes, "SourcePacketRepository", FakeRepository)

    response = await source_packet_routes.create_source_packet(
        source_request(),
        request_for_workspace("server-workspace"),
    )

    packet = captured["packet"]
    assert captured["db"] is fake_db
    assert packet.workspace_id == "server-workspace"
    assert packet.packet_id
    assert response["workspace_id"] == "server-workspace"
    assert response["packet_id"] == packet.packet_id


@pytest.mark.asyncio
async def test_quick_capture_creates_explicit_user_assertions_and_bound_allowed_facts(monkeypatch):
    captured = {}

    class FakeRepository:
        def __init__(self, db):
            captured["db"] = db

        async def create(self, packet):
            captured["packet"] = packet
            return packet

    monkeypatch.setattr(source_packet_routes, "get_db", lambda: object())
    monkeypatch.setattr(source_packet_routes, "SourcePacketRepository", FakeRepository)

    response = await source_packet_routes.create_quick_source_packet(
        QuickSourcePacketRequest(
            title="Create Studio evidence",
            facts=[
                "CI #550 passed all four release jobs.",
                "The visual renderer keeps technical diagrams deterministic.",
            ],
        ),
        request_for_workspace("server-workspace"),
    )

    packet = captured["packet"]
    assert response["packet_id"] == packet.packet_id
    assert packet.workspace_id == "server-workspace"
    assert packet.strict_mode is True
    assert len(packet.evidence) == 2
    assert len(packet.allowed_facts) == 2

    for index, (evidence, fact) in enumerate(zip(packet.evidence, packet.allowed_facts), start=1):
        assert evidence.authority == SourceAuthority.USER_PROVIDED
        assert evidence.source_type == SourceType.USER_ASSERTION
        assert evidence.metadata["capture_surface"] == "create_studio_quick_evidence"
        assert fact.statement == evidence.excerpt
        assert fact.source_refs == [evidence.evidence_id]
        assert evidence.evidence_id == f"user-fact-evidence-{index:02d}"


def test_quick_capture_contract_rejects_duplicate_or_oversized_facts():
    with pytest.raises(ValidationError):
        QuickSourcePacketRequest(title="Evidence", facts=["same", "same"])

    with pytest.raises(ValidationError):
        QuickSourcePacketRequest(title="Evidence", facts=["x" * 1001])


@pytest.mark.asyncio
async def test_list_source_packets_is_workspace_scoped_and_exposes_metadata_only(monkeypatch):
    calls = []
    packet = SourcePacket(
        packet_id="packet-1",
        workspace_id="server-workspace",
        title="Release evidence",
        summary="Exact-head certification evidence",
        evidence=[
            EvidenceRef(
                evidence_id="secret-evidence",
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.USER_ASSERTION,
                excerpt="Sensitive evidence text should not be in list metadata.",
            )
        ],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-1",
                statement="A bounded fact",
                source_refs=["secret-evidence"],
            )
        ],
    )

    class FakeRepository:
        def __init__(self, db):
            pass

        async def list_recent(self, workspace_id, limit):
            calls.append((workspace_id, limit))
            return [packet]

    monkeypatch.setattr(source_packet_routes, "get_db", lambda: object())
    monkeypatch.setattr(source_packet_routes, "SourcePacketRepository", FakeRepository)

    response = await source_packet_routes.list_source_packets(
        request_for_workspace("server-workspace"),
        limit=10,
    )
    payload = response.model_dump(mode="json")

    assert calls == [("server-workspace", 10)]
    assert payload["count"] == 1
    summary = payload["packets"][0]
    assert summary["packet_id"] == "packet-1"
    assert summary["evidence_count"] == 1
    assert summary["allowed_fact_count"] == 1
    assert "evidence" not in summary
    assert "allowed_facts" not in summary
    assert "Sensitive evidence text" not in str(summary)


@pytest.mark.asyncio
async def test_get_source_packet_is_scoped_to_authoritative_workspace(monkeypatch):
    calls = []
    packet = SourcePacket(
        packet_id="packet-1",
        workspace_id="server-workspace",
        title="Packet",
    )

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            calls.append((workspace_id, packet_id))
            return packet

    monkeypatch.setattr(source_packet_routes, "get_db", lambda: object())
    monkeypatch.setattr(source_packet_routes, "SourcePacketRepository", FakeRepository)

    response = await source_packet_routes.get_source_packet(
        "packet-1",
        request_for_workspace("server-workspace"),
    )

    assert calls == [("server-workspace", "packet-1")]
    assert response["packet_id"] == "packet-1"


@pytest.mark.asyncio
async def test_get_source_packet_does_not_reveal_cross_workspace_or_unknown_packet(monkeypatch):
    calls = []

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            calls.append((workspace_id, packet_id))
            return None

    monkeypatch.setattr(source_packet_routes, "get_db", lambda: object())
    monkeypatch.setattr(source_packet_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await source_packet_routes.get_source_packet(
            "possibly-cross-workspace",
            request_for_workspace("server-workspace"),
        )

    assert calls == [("server-workspace", "possibly-cross-workspace")]
    assert exc.value.status_code == 404
    assert exc.value.detail == "Source packet not found"


@pytest.mark.asyncio
async def test_source_packet_routes_fail_closed_without_durable_database(monkeypatch):
    monkeypatch.setattr(source_packet_routes, "get_db", lambda: None)
    request = request_for_workspace("server-workspace")

    with pytest.raises(HTTPException) as create_exc:
        await source_packet_routes.create_source_packet(source_request(), request)
    assert create_exc.value.status_code == 503

    with pytest.raises(HTTPException) as quick_exc:
        await source_packet_routes.create_quick_source_packet(
            QuickSourcePacketRequest(title="Evidence", facts=["A fact"]),
            request,
        )
    assert quick_exc.value.status_code == 503

    with pytest.raises(HTTPException) as list_exc:
        await source_packet_routes.list_source_packets(request, limit=25)
    assert list_exc.value.status_code == 503

    with pytest.raises(HTTPException) as get_exc:
        await source_packet_routes.get_source_packet("packet-1", request)
    assert get_exc.value.status_code == 503
