from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from core.linkedin import LinkedInPublishError, LinkedInPublisherConfig
from db.mongo import get_db
from models.content_run import ContentRunScheduleRequest, ContentRunStatus


router = APIRouter(tags=["scheduling"])


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


@router.post("/content-runs/{run_id}/schedule")
async def schedule_content_run(run_id: str, req: ContentRunScheduleRequest):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    now = datetime.now(timezone.utc)
    scheduled_for = req.scheduled_for.astimezone(timezone.utc)
    if scheduled_for <= now:
        raise HTTPException(status_code=422, detail="scheduled_for must be in the future")

    try:
        LinkedInPublisherConfig.from_env()
    except LinkedInPublishError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Only APPROVED content can be scheduled; current status is {existing.get('status')}",
        )
    approval = existing.get("approval")
    if not isinstance(approval, dict):
        raise HTTPException(status_code=409, detail="Content run has no immutable approval snapshot")

    schedule = {
        "schedule_id": str(uuid4()),
        "status": "SCHEDULED",
        "scheduled_for": scheduled_for,
        "approval_id": approval["approval_id"],
        "bundle_sha256": approval["bundle_sha256"],
        "created_at": now,
        "claimed_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "error_message": None,
    }
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.APPROVED.value,
            "approval.approval_id": approval["approval_id"],
            "approval.bundle_sha256": approval["bundle_sha256"],
        },
        {"$set": {
            "status": ContentRunStatus.SCHEDULED.value,
            "schedule": schedule,
            "updated_at": now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed before scheduling could be applied")

    return _serialize(await collection.find_one({"run_id": run_id}))


@router.delete("/content-runs/{run_id}/schedule")
async def cancel_content_schedule(run_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.SCHEDULED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Only SCHEDULED content can be cancelled; current status is {existing.get('status')}",
        )

    schedule = existing.get("schedule") or {}
    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.SCHEDULED.value,
            "schedule.schedule_id": schedule.get("schedule_id"),
        },
        {"$set": {
            "status": ContentRunStatus.APPROVED.value,
            "schedule.status": "CANCELLED",
            "schedule.cancelled_at": now,
            "updated_at": now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Schedule was claimed before cancellation completed")
    return _serialize(await collection.find_one({"run_id": run_id}))
