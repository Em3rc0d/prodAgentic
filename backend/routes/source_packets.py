import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from db.mongo import get_db
from db.source_packets import SourcePacketRepository
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourcePacketCreateRequest,
    SourceType,
)
from models.source_packet import (
    QuickSourcePacketRequest,
    SourcePacketListResponse,
    SourcePacketSummary,
)


router = APIRouter(tags=["source-packets"])


def _workspace_id(request: Request) -> str:
    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    workspace_id = getattr(settings, "app_workspace_id", None)
    if not isinstance(workspace_id, str) or not workspace_id:
        raise HTTPException(status_code=503, detail="Authoritative workspace configuration is unavailable")
    return workspace_id


def _summary(packet: SourcePacket) -> SourcePacketSummary:
    return SourcePacketSummary(
        packet_id=packet.packet_id,
        title=packet.title,
        summary=packet.summary,
        strict_mode=packet.strict_mode,
        evidence_count=len(packet.evidence),
        allowed_fact_count=len(packet.allowed_facts),
        allowed_inference_count=len(packet.allowed_inferences),
        created_at=packet.created_at,
    )


@router.get("/source-packets", response_model=SourcePacketListResponse)
async def list_source_packets(
    request: Request,
    limit: int = Query(25, ge=1, le=50),
) -> SourcePacketListResponse:
    """List packet metadata for the authoritative workspace without re-exposing evidence."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable source packets")

    packets = await SourcePacketRepository(db).list_recent(_workspace_id(request), limit)
    summaries = [_summary(packet) for packet in packets]
    return SourcePacketListResponse(packets=summaries, count=len(summaries))


@router.post("/source-packets", response_model=SourcePacket)
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


@router.post("/source-packets/quick", response_model=SourcePacket)
async def create_quick_source_packet(req: QuickSourcePacketRequest, request: Request):
    """Create an immutable packet from explicit user-authored factual statements.

    The quick path does not reinterpret arbitrary pasted evidence. The submitted
    field is explicitly a list of facts; each fact is stored both as inspectable
    USER_ASSERTION evidence and as an allowed fact bound to that evidence.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable source packets")

    captured_at = datetime.now(timezone.utc)
    evidence: list[EvidenceRef] = []
    allowed_facts: list[EvidenceBoundStatement] = []
    for index, fact in enumerate(req.facts, start=1):
        evidence_id = f"user-fact-evidence-{index:02d}"
        statement_id = f"user-fact-{index:02d}"
        evidence.append(
            EvidenceRef(
                evidence_id=evidence_id,
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.USER_ASSERTION,
                excerpt=fact,
                captured_at=captured_at,
                metadata={"capture_surface": "create_studio_quick_evidence"},
            )
        )
        allowed_facts.append(
            EvidenceBoundStatement(
                statement_id=statement_id,
                statement=fact,
                source_refs=[evidence_id],
            )
        )

    packet = SourcePacket(
        packet_id=str(uuid.uuid4()),
        workspace_id=_workspace_id(request),
        title=req.title,
        summary=req.summary,
        strict_mode=req.strict_mode,
        evidence=evidence,
        allowed_facts=allowed_facts,
        created_at=captured_at,
    )
    await SourcePacketRepository(db).create(packet)
    return packet.model_dump(mode="json")


@router.get("/source-packets/{packet_id}", response_model=SourcePacket)
async def get_source_packet(packet_id: str, request: Request):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable source packets")

    packet = await SourcePacketRepository(db).get(_workspace_id(request), packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Source packet not found")
    return packet.model_dump(mode="json")
