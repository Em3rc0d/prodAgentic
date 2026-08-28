import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from core.content_identity import build_content_identity
from core.content_memory import ContentMemoryService
from core.grounding import GroundingAssessmentBuilder, GroundingPolicy
from db.mongo import get_db
from models.content_run import ContentRunApprovalRequest, ContentRunEditRequest, ContentRunStatus
from models.grounding import (
    GroundingAssessment,
    GroundingDecision,
    GroundingDraftEvaluationRequest,
    GroundingEvaluationRequest,
    GroundingReviewDecision,
    GroundingReviewRequest,
    GroundingReviewSnapshot,
    SourcePacket,
)


router = APIRouter(tags=["content-runs"])

_EDITABLE_STATUSES = {
    ContentRunStatus.TEXT_READY.value,
    ContentRunStatus.READY_FOR_REVIEW.value,
}


def _serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value) -> str:
    canonical = json.dumps(
        _serialize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(canonical)


def _load_grounding_material(existing: dict):
    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for grounding")

    source_packet_doc = existing.get("source_packet")
    assessment_doc = existing.get("grounding_assessment")
    if not isinstance(source_packet_doc, dict) or not isinstance(assessment_doc, dict):
        raise HTTPException(status_code=409, detail="Current content requires a Grounding assessment")

    try:
        source_packet = SourcePacket.model_validate(source_packet_doc)
        assessment = GroundingAssessment.model_validate(assessment_doc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Stored Grounding evidence is invalid: {exc}") from exc

    if source_packet.workspace_id != (existing.get("workspace_id") or "legacy-default"):
        raise HTTPException(status_code=409, detail="Grounding source packet does not belong to this workspace")

    final_content_sha256 = _sha256_text(final_content)
    if assessment.content_sha256 != final_content_sha256:
        raise HTTPException(status_code=409, detail="Grounding assessment is stale relative to final content")

    gate = GroundingPolicy.evaluate(assessment, source_packet)
    source_packet_sha256 = _sha256_json(source_packet.model_dump(mode="python"))
    assessment_sha256 = _sha256_json(assessment.model_dump(mode="python"))
    gate_sha256 = _sha256_json(gate.model_dump(mode="python"))

    return {
        "source_packet": source_packet,
        "assessment": assessment,
        "gate": gate,
        "final_content_sha256": final_content_sha256,
        "source_packet_sha256": source_packet_sha256,
        "assessment_sha256": assessment_sha256,
        "gate_sha256": gate_sha256,
    }


def _require_verified_grounding(existing: dict) -> dict:
    material = _load_grounding_material(existing)
    gate = material["gate"]
    if gate.decision != GroundingDecision.PASS:
        reason = "; ".join(gate.reasons) or "Grounding policy blocked this content"
        raise HTTPException(status_code=409, detail=f"Grounding BLOCK: {reason}")

    review_doc = existing.get("grounding_review")
    if not isinstance(review_doc, dict):
        raise HTTPException(status_code=409, detail="Explicit human Grounding verification is required before approval")

    try:
        review = GroundingReviewSnapshot.model_validate(review_doc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Stored Grounding review is invalid: {exc}") from exc

    if review.decision != GroundingReviewDecision.VERIFIED:
        raise HTTPException(status_code=409, detail="Grounding review is not VERIFIED")
    if review.content_sha256 != material["final_content_sha256"]:
        raise HTTPException(status_code=409, detail="Grounding review is stale relative to final content")
    if review.source_packet_sha256 != material["source_packet_sha256"]:
        raise HTTPException(status_code=409, detail="Grounding review is stale relative to the current source evidence")
    if review.assessment_sha256 != material["assessment_sha256"]:
        raise HTTPException(status_code=409, detail="Grounding review is stale relative to the current assessment")
    if review.policy_version != gate.policy_version:
        raise HTTPException(status_code=409, detail="Grounding policy changed after human verification")

    material["review"] = review
    material["review_sha256"] = _sha256_json(review.model_dump(mode="python"))
    return material


def _build_approval_snapshot(existing: dict, include_visual: bool) -> dict:
    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for approval")

    grounding = _require_verified_grounding(existing)

    visual_render = None
    visual_render_sha256 = None

    if include_visual:
        current_visual = existing.get("visual_render")
        if not current_visual or current_visual.get("status") != "READY":
            raise HTTPException(status_code=409, detail="A READY visual artifact is required for visual approval")
        if not current_visual.get("asset_url") or not current_visual.get("asset_sha256"):
            raise HTTPException(status_code=409, detail="Visual artifact is missing immutable asset evidence")
        if current_visual.get("requested_prompt") != (existing.get("visual_prompt") or ""):
            raise HTTPException(status_code=409, detail="Visual artifact is stale relative to the current visual prompt")

        visual_render = deepcopy(current_visual)
        visual_render_sha256 = _sha256_json(visual_render)

    final_content_sha256 = _sha256_text(final_content)
    bundle_sha256 = _sha256_json({
        "include_visual": include_visual,
        "final_content_sha256": final_content_sha256,
        "visual_render_sha256": visual_render_sha256,
        "source_packet_sha256": grounding["source_packet_sha256"],
        "grounding_assessment_sha256": grounding["assessment_sha256"],
        "grounding_gate_sha256": grounding["gate_sha256"],
        "grounding_review_sha256": grounding["review_sha256"],
        "grounding_policy_version": grounding["gate"].policy_version,
    })

    return {
        "approval_id": str(uuid.uuid4()),
        "approved_at": datetime.now(timezone.utc),
        "source": "explicit_user_action",
        "include_visual": include_visual,
        "final_content": final_content,
        "final_content_sha256": final_content_sha256,
        "visual_render": visual_render,
        "visual_render_sha256": visual_render_sha256,
        "source_packet_sha256": grounding["source_packet_sha256"],
        "grounding_assessment_sha256": grounding["assessment_sha256"],
        "grounding_gate_sha256": grounding["gate_sha256"],
        "grounding_review_sha256": grounding["review_sha256"],
        "grounding_policy_version": grounding["gate"].policy_version,
        "bundle_sha256": bundle_sha256,
    }


async def _refresh_memory_for_approval(db, run_id: str) -> dict:
    """Return a review run whose memory hash matches its current final content.

    Memory writes intentionally do not touch root updated_at. Any concurrent
    human edit/render after this function still causes the existing optimistic
    approval update to miss.
    """
    collection = db["content_runs"]
    memory = ContentMemoryService(db=db)

    for _ in range(3):
        await memory.refresh_review(run_id)
        existing = await collection.find_one({"run_id": run_id})
        if existing is None:
            raise HTTPException(status_code=404, detail="Content run not found")
        if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
            raise HTTPException(
                status_code=409,
                detail=f"Only READY_FOR_REVIEW content can be approved; current status is {existing.get('status')}",
            )

        final_content = existing.get("final_content")
        if not isinstance(final_content, str) or not final_content.strip():
            raise HTTPException(status_code=409, detail="Final content is not ready for approval")
        identity = build_content_identity(final_content)
        memory_check = existing.get("memory_check") or {}
        if memory_check.get("normalized_sha256") == identity.normalized_sha256:
            return existing

    raise HTTPException(status_code=409, detail="Content memory could not synchronize with the current review revision")


@router.get("/content-runs")
async def list_content_runs(
    limit: int = Query(25, ge=1, le=100),
    status: ContentRunStatus | None = Query(None),
):
    db = get_db()
    if db is None:
        return {"runs": [], "count": 0, "message": "MongoDB not connected — runs not persisted"}

    query = {"status": status.value} if status else {}
    cursor = db["content_runs"].find(query).sort("created_at", -1).limit(limit)
    runs = []
    async for doc in cursor:
        runs.append(_serialize(doc))

    return {"runs": runs, "count": len(runs)}


@router.get("/content-runs/{run_id}")
async def get_content_run(run_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    doc = await db["content_runs"].find_one({"run_id": run_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Content run not found")

    return _serialize(doc)


@router.patch("/content-runs/{run_id}")
async def edit_content_run(run_id: str, req: ContentRunEditRequest):
    """Persist human edits without rewriting generated provenance."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")

    if existing.get("status") not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Content run cannot be edited while status is {existing.get('status')}",
        )

    updates = {"updated_at": datetime.now(timezone.utc)}
    if req.final_content is not None:
        updated_final_content = req.final_content.strip()
        updates["final_content"] = updated_final_content
        if updated_final_content != (existing.get("final_content") or ""):
            # Grounding is revision-bound. A previously valid assessment/review
            # may not survive even a one-character edit to publishable text.
            updates["grounding_assessment"] = None
            updates["grounding_gate"] = None
            updates["grounding_review"] = None
    if req.visual_prompt is not None:
        updates["visual_prompt"] = req.visual_prompt
        if req.visual_prompt != (existing.get("visual_prompt") or ""):
            updates["visual_render"] = None

    await collection.update_one({"run_id": run_id}, {"$set": updates})

    if req.final_content is not None:
        await db["posts"].update_one(
            {"run_id": run_id},
            {"$set": {"final_content": updates["final_content"]}},
        )
        await ContentMemoryService(db=db).refresh_review(run_id)

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)


@router.post("/content-runs/{run_id}/grounding/evaluate")
async def evaluate_content_run_grounding(run_id: str, req: GroundingEvaluationRequest):
    """Persist an inspectable claim/evidence assessment for the exact review revision."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(status_code=409, detail="Grounding evaluation requires READY_FOR_REVIEW content")

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for grounding")

    workspace_id = existing.get("workspace_id") or "legacy-default"
    if req.source_packet.workspace_id != workspace_id:
        raise HTTPException(status_code=409, detail="Source packet workspace does not match ContentRun workspace")

    current_content_sha256 = _sha256_text(final_content)
    if req.assessment.content_sha256 != current_content_sha256:
        raise HTTPException(status_code=409, detail="Grounding assessment does not match current final content")

    gate = GroundingPolicy.evaluate(req.assessment, req.source_packet)
    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {"$set": {
            "source_packet": req.source_packet.model_dump(mode="python"),
            "grounding_assessment": req.assessment.model_dump(mode="python"),
            "grounding_gate": gate.model_dump(mode="python"),
            "grounding_review": None,
            "updated_at": now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed while Grounding was being evaluated")

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)


@router.post("/content-runs/{run_id}/grounding/evaluate-draft")
async def evaluate_content_run_grounding_draft(run_id: str, req: GroundingDraftEvaluationRequest):
    """Derive and persist authoritative Grounding state from semantic proposals."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(status_code=409, detail="Grounding draft evaluation requires READY_FOR_REVIEW content")

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for grounding")

    workspace_id = existing.get("workspace_id") or "legacy-default"
    if req.source_packet.workspace_id != workspace_id:
        raise HTTPException(status_code=409, detail="Source packet workspace does not match ContentRun workspace")

    current_content_sha256 = _sha256_text(final_content)
    if req.draft.content_sha256 != current_content_sha256:
        raise HTTPException(status_code=409, detail="Grounding draft does not match current final content")

    try:
        assessment = GroundingAssessmentBuilder.build(req.draft, req.source_packet)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Grounding draft is invalid: {exc}") from exc

    gate = GroundingPolicy.evaluate(assessment, req.source_packet)
    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {"$set": {
            "source_packet": req.source_packet.model_dump(mode="python"),
            "grounding_assessment": assessment.model_dump(mode="python"),
            "grounding_gate": gate.model_dump(mode="python"),
            "grounding_review": None,
            "updated_at": now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed while Grounding draft was being evaluated")

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)


@router.post("/content-runs/{run_id}/grounding/review")
async def review_content_run_grounding(run_id: str, req: GroundingReviewRequest):
    """Record the explicit human decision over the current claim/evidence map."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(status_code=409, detail="Grounding review requires READY_FOR_REVIEW content")

    material = _load_grounding_material(existing)
    gate = material["gate"]
    if req.decision == GroundingReviewDecision.VERIFIED and gate.decision != GroundingDecision.PASS:
        reason = "; ".join(gate.reasons) or "Grounding policy blocked this content"
        raise HTTPException(status_code=409, detail=f"Cannot verify Grounding while policy is BLOCK: {reason}")

    review = GroundingReviewSnapshot(
        review_id=str(uuid.uuid4()),
        decision=req.decision,
        content_sha256=material["final_content_sha256"],
        source_packet_sha256=material["source_packet_sha256"],
        assessment_sha256=material["assessment_sha256"],
        policy_version=gate.policy_version,
        warning_claim_ids=gate.warning_claim_ids,
    )
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {"$set": {
            "grounding_gate": gate.model_dump(mode="python"),
            "grounding_review": review.model_dump(mode="python"),
            "updated_at": review.reviewed_at,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed while Grounding review was being applied")

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)


@router.post("/content-runs/{run_id}/approve")
async def approve_content_run(run_id: str, req: ContentRunApprovalRequest):
    """Freeze the exact publishable bundle behind explicit human approval and verified Grounding."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")

    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail=f"Only READY_FOR_REVIEW content can be approved; current status is {existing.get('status')}",
        )

    existing = await _refresh_memory_for_approval(db, run_id)
    approval = _build_approval_snapshot(existing, req.include_visual)
    now = approval["approved_at"]

    # Optimistic concurrency: every review edit, render, Grounding evaluation,
    # and Grounding review changes updated_at. If the run changes after we build
    # the approval snapshot, this query misses instead of approving stale data.
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {"$set": {
            "status": ContentRunStatus.APPROVED.value,
            "approval": approval,
            "updated_at": now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed while approval was being applied")

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)