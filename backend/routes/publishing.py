from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from core.linkedin import LinkedInPublishError, LinkedInPublisherConfig
from core.publication import (
    PublicationConflict,
    PublicationCoordinator,
    PublicationFailed,
    PublicationReconciliationRequired,
    PublicationUnavailable,
)
from db.mongo import get_db


router = APIRouter(tags=["publishing"])


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


@router.get("/publishing/linkedin/status")
async def linkedin_publisher_status():
    try:
        config = LinkedInPublisherConfig.from_env()
        return {"configured": True, "author_urn": config.author_urn, "api_version": config.api_version}
    except LinkedInPublishError as exc:
        return {"configured": False, "reason": str(exc)}


@router.post("/content-runs/{run_id}/publish")
async def publish_content_run(run_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    try:
        updated = await PublicationCoordinator(db).publish_run(run_id)
        return _serialize(updated)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublicationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PublicationReconciliationRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PublicationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PublicationFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
