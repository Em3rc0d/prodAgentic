import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from db.mongo import get_db
from db.source_packets import SourcePacketRepository
from models.grounding import SourcePacket, SourcePacketCreateRequest


router = APIRouter(tags=["source-packets"])


def _workspace_id(request: Request) -> str:
    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    workspace_id = getattr(settings, "app_workspace_id", None)
    if not isinstance(workspace_id, str) or not workspace_id:
        raise HTTPException(status_code=503, detail="Authoritative workspace configuration is unavailable")
    return workspace_id


@router.post("/source-packets")
async def create_source_packet(req: SourcePacketCreateRequest, request: Request):
    """Create an immutable server-scoped evidence packet for later generation."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable source packets")

    packet = SourcePacket(
        packet_id=str(uuid.uuid4()),
        workspace_id=_workspace_id(request),
        title=req.title,
        summary=req.summary,
        strict_mode=req.strict_mode,
        evidence=req.evidence,
        allowed_facts=req.allowed_facts,
        allowed_inferences=req.allowed_inferences,
        prohibited_claims=req.prohibited_claims,
        created_at=datetime.now(timezone.utc),
    )
    await SourcePacketRepository(db).create(packet)
    return packet.model_dump(mode="json")


@router.get("/source-packets/{packet_id}")
async def get_source_packet(packet_id: str, request: Request):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable source packets")

    packet = await SourcePacketRepository(db).get(_workspace_id(request), packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Source packet not found")
    return packet.model_dump(mode="json")
