from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from db.mongo import get_db
from models.content_run import ContentRunStatus


router = APIRouter(tags=["content-runs"])


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
