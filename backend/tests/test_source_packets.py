from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.source_packets as source_packet_routes
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourcePacketCreateRequest,
    SourceType,
)


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

    with pytest.raises(HTTPException) as create_exc:
        await source_packet_routes.create_source_packet(
            source_request(),
            request_for_workspace("server-workspace"),
        )
    assert create_exc.value.status_code == 503

    with pytest.raises(HTTPException) as get_exc:
        await source_packet_routes.get_source_packet(
            "packet-1",
            request_for_workspace("server-workspace"),
        )
    assert get_exc.value.status_code == 503
