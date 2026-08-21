from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from db.mongo import get_db
from models.content_run import ContentRunEditRequest, ContentRunStatus


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
    """Persist human edits without rewriting generated provenance.

    Only pre-approval review states are mutable. Approval/publication slices can
    therefore rely on this endpoint never changing an immutable published asset.
    """
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
        updates["final_content"] = req.final_content.strip()
    if req.visual_prompt is not None:
        updates["visual_prompt"] = req.visual_prompt

    await collection.update_one({"run_id": run_id}, {"$set": updates})

    # Keep the legacy post projection coherent while it exists.
    if req.final_content is not None:
        await db["posts"].update_one(
            {"run_id": run_id},
            {"$set": {"final_content": updates["final_content"]}},
        )

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)
