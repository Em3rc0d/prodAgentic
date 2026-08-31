from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from agents.adapters.semantic_matcher import SemanticMatcherProtocolError
from agents.adapters.types import ModelExecutionError
from core.grounding import GroundingAssessmentBuilder, GroundingPolicy
from core.semantic_matcher import SemanticMatcherBoundary
from db.mongo import get_db
from db.source_packets import SourcePacketRepository
from models.content_run import ContentRunStatus
from models.grounding import SourcePacket
from models.semantic_matcher import SemanticMatcherInput
from routes.claim_extractor import require_verified_claim_extraction


router = APIRouter(tags=["review-cockpit"])


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/content-runs/{run_id}/grounding/match-evaluate-current")
async def match_evaluate_current_generation_evidence(run_id: str, request: Request):
    """Run semantic matching and deterministic Grounding against server-owned evidence.

    This route exists for product review flows that must not round-trip evidence
    authority or semantic proposals through a client-controlled request body.

    The human must first verify claim-extraction completeness. The server then:
    1. resolves the exact pre-generation SourcePacket from the run;
    2. reloads that immutable packet from the workspace-scoped repository;
    3. asks the semantic matcher only for claim/evidence relation proposals;
    4. freezes the proposal draft;
    5. derives GroundingAssessment + GroundingPolicy deterministically; and
    6. invalidates any prior human Grounding review.

    Human Grounding verification remains a separate downstream action.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for review cockpit Grounding")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Review cockpit Grounding requires READY_FOR_REVIEW content",
        )

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for Grounding")

    extraction = require_verified_claim_extraction(existing)

    generation_packet_doc = existing.get("generation_source_packet")
    if not isinstance(generation_packet_doc, dict):
        raise HTTPException(
            status_code=409,
            detail="Evidence-fed generation SourcePacket is required for current-evidence Grounding",
        )
    try:
        generation_packet = SourcePacket.model_validate(generation_packet_doc)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Stored generation SourcePacket is invalid: {exc}",
        ) from exc

    workspace_id = existing.get("workspace_id") or "legacy-default"
    if generation_packet.workspace_id != workspace_id:
        raise HTTPException(
            status_code=409,
            detail="Generation SourcePacket workspace does not match ContentRun workspace",
        )

    source_packet = await SourcePacketRepository(db).get(
        workspace_id,
        generation_packet.packet_id,
    )
    if source_packet is None:
        # Keep unknown and cross-workspace packet behavior indistinguishable.
        raise HTTPException(status_code=404, detail="Source packet not found")

    if source_packet.model_dump(mode="json") != generation_packet.model_dump(mode="json"):
        raise HTTPException(
            status_code=409,
            detail="Generation SourcePacket no longer matches its immutable repository snapshot",
        )

    container = getattr(request.app.state, "container", None)
    matcher = getattr(container, "semantic_matcher", None)
    if matcher is None:
        raise HTTPException(status_code=503, detail="Semantic matcher provider is unavailable")

    matcher_input = SemanticMatcherInput(
        packet_id=source_packet.packet_id,
        content_sha256=_sha256_text(final_content),
        claims=extraction.claims,
    )

    try:
        matcher_output = await matcher.match(matcher_input, source_packet)
        draft = SemanticMatcherBoundary.to_grounding_draft(
            matcher_input,
            matcher_output,
            source_packet,
            extraction_complete=True,
        )
        assessment = GroundingAssessmentBuilder.build(draft, source_packet)
        gate = GroundingPolicy.evaluate(assessment, source_packet)
    except ModelExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Semantic matcher provider failed: {exc.category.value}",
        ) from exc
    except (SemanticMatcherProtocolError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Semantic Grounding failed closed: {exc}",
        ) from exc

    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {
            "$set": {
                "grounding_match_draft": draft.model_dump(mode="python"),
                "source_packet": source_packet.model_dump(mode="python"),
                "grounding_assessment": assessment.model_dump(mode="python"),
                "grounding_gate": gate.model_dump(mode="python"),
                "grounding_review": None,
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Content run changed while semantic Grounding was being evaluated",
        )

    return {
        "draft": draft.model_dump(mode="json"),
        "assessment": assessment.model_dump(mode="json"),
        "gate": gate.model_dump(mode="json"),
    }
