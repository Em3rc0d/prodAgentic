import hashlib

from fastapi import APIRouter, HTTPException, Request

from agents.adapters.remediator import RemediatorProtocolError
from agents.adapters.types import ModelExecutionError
from core.remediation import RemediationPolicy
from db.mongo import get_db
from models.content_run import ContentRunStatus
from models.grounding import GroundingAssessment, SourcePacket


router = APIRouter(tags=["grounding-remediation"])


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/content-runs/{run_id}/grounding/remediation-draft")
async def propose_content_run_remediation(run_id: str, request: Request):
    """Return advisory SOFTEN/REMOVE proposals for the current blocked assessment.

    This endpoint never mutates final_content and never persists Grounding or
    remediation authority. Any accepted wording change must go through an
    explicit content edit and then the full extraction/matching/Grounding cycle.
    """

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for Grounding remediation")

    existing = await db["content_runs"].find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Grounding remediation requires READY_FOR_REVIEW content",
        )

    final_content = existing.get("final_content")
    source_packet_doc = existing.get("source_packet")
    assessment_doc = existing.get("grounding_assessment")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for remediation")
    if not isinstance(source_packet_doc, dict) or not isinstance(assessment_doc, dict):
        raise HTTPException(
            status_code=409,
            detail="Current content requires a Grounding assessment before remediation",
        )

    try:
        source_packet = SourcePacket.model_validate(source_packet_doc)
        assessment = GroundingAssessment.model_validate(assessment_doc)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Stored Grounding material is invalid: {exc}",
        ) from exc

    workspace_id = existing.get("workspace_id") or "legacy-default"
    if source_packet.workspace_id != workspace_id:
        raise HTTPException(
            status_code=409,
            detail="Grounding source packet does not belong to this workspace",
        )
    if assessment.content_sha256 != _sha256_text(final_content):
        raise HTTPException(
            status_code=409,
            detail="Grounding assessment is stale relative to final content",
        )

    container = getattr(request.app.state, "container", None)
    remediator = getattr(container, "remediator", None)
    if remediator is None:
        raise HTTPException(status_code=503, detail="Grounding remediator provider is unavailable")

    try:
        draft = await remediator.remediate(assessment, source_packet)
        gate = RemediationPolicy.evaluate(draft, assessment, source_packet)
    except ModelExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Grounding remediator provider failed: {exc.category.value}",
        ) from exc
    except (RemediatorProtocolError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Grounding remediation failed closed: {exc}",
        ) from exc

    if not gate.valid:
        raise HTTPException(
            status_code=502,
            detail="Grounding remediator output failed deterministic remediation policy: "
            + "; ".join(gate.reasons),
        )

    return {
        "draft": draft.model_dump(mode="json"),
        "gate": gate.model_dump(mode="json"),
        "advisory_only": True,
        "auto_applied": False,
        "requires_explicit_edit_and_full_regrounding": gate.requires_regrounding,
    }
