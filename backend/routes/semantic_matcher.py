import hashlib

from fastapi import APIRouter, HTTPException, Request

from agents.adapters.semantic_matcher import SemanticMatcherProtocolError
from agents.adapters.types import ModelExecutionError
from core.semantic_matcher import SemanticMatcherBoundary
from db.mongo import get_db
from db.source_packets import SourcePacketRepository
from models.content_run import ContentRunStatus
from models.semantic_matcher import SemanticMatchDraftRequest, SemanticMatcherInput


router = APIRouter(tags=["grounding-semantic-matcher"])


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/content-runs/{run_id}/grounding/match-draft")
async def match_content_run_grounding_draft(
    run_id: str,
    req: SemanticMatchDraftRequest,
    request: Request,
):
    """Return a provider-generated Grounding draft without persisting authority.

    The semantic provider remains advisory. This endpoint never writes
    Grounding state to the ContentRun; callers must pass the returned draft
    through the existing deterministic evaluate-draft endpoint separately.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for semantic Grounding")

    existing = await db["content_runs"].find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Semantic Grounding matching requires READY_FOR_REVIEW content",
        )

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for grounding")

    workspace_id = existing.get("workspace_id") or "legacy-default"
    source_packet = await SourcePacketRepository(db).get(workspace_id, req.packet_id)
    if source_packet is None:
        # Do not distinguish unknown IDs from cross-workspace IDs.
        raise HTTPException(status_code=404, detail="Source packet not found")

    container = getattr(request.app.state, "container", None)
    matcher = getattr(container, "semantic_matcher", None)
    if matcher is None:
        raise HTTPException(status_code=503, detail="Semantic matcher provider is unavailable")

    matcher_input = SemanticMatcherInput(
        packet_id=source_packet.packet_id,
        content_sha256=_sha256_text(final_content),
        claims=req.claims,
    )

    try:
        matcher_output = await matcher.match(matcher_input, source_packet)
        draft = SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            source_packet,
            extraction_complete=req.extraction_complete,
        )
    except ModelExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Semantic matcher provider failed: {exc.category.value}",
        ) from exc
    except (SemanticMatcherProtocolError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Semantic matcher failed closed: {exc}",
        ) from exc

    return draft.model_dump(mode="json")
