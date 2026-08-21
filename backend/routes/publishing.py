from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from core.linkedin import LinkedInPublishError, LinkedInPublisher, LinkedInPublisherConfig
from db.mongo import get_db
from models.content_run import ContentRunStatus


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
        return {
            "configured": True,
            "author_urn": config.author_urn,
            "api_version": config.api_version,
        }
    except LinkedInPublishError as exc:
        return {"configured": False, "reason": str(exc)}


@router.post("/content-runs/{run_id}/publish")
async def publish_content_run(run_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")

    approval = existing.get("approval")
    if not isinstance(approval, dict):
        raise HTTPException(status_code=409, detail="Content run has no immutable approval snapshot")

    existing_publication = existing.get("publication") or {}
    if (
        existing.get("status") == ContentRunStatus.PUBLISHED.value
        and existing_publication.get("status") == "PUBLISHED"
        and existing_publication.get("bundle_sha256") == approval.get("bundle_sha256")
    ):
        return _serialize(existing)

    if existing.get("status") == ContentRunStatus.PUBLISHING.value:
        raise HTTPException(
            status_code=409,
            detail="Publication is already in progress or requires reconciliation before retry",
        )

    if existing.get("status") != ContentRunStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Only APPROVED content can be published; current status is {existing.get('status')}",
        )

    try:
        config = LinkedInPublisherConfig.from_env()
    except LinkedInPublishError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    attempt_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    publication = {
        "provider": "linkedin",
        "status": "PUBLISHING",
        "attempt_id": attempt_id,
        "approval_id": approval["approval_id"],
        "bundle_sha256": approval["bundle_sha256"],
        "author_urn": config.author_urn,
        "started_at": started_at,
        "completed_at": None,
        "external_post_urn": None,
        "external_image_urn": None,
        "error_message": None,
    }

    claim = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.APPROVED.value,
            "approval.approval_id": approval["approval_id"],
            "approval.bundle_sha256": approval["bundle_sha256"],
        },
        {"$set": {
            "status": ContentRunStatus.PUBLISHING.value,
            "publication": publication,
            "updated_at": started_at,
        }},
    )
    if claim.matched_count == 0:
        raise HTTPException(status_code=409, detail="Content run changed before publication could be claimed")

    publisher = LinkedInPublisher(config)
    try:
        result = await publisher.publish(approval)
    except LinkedInPublishError as exc:
        failed_at = datetime.now(timezone.utc)
        await collection.update_one(
            {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
            {"$set": {
                "status": ContentRunStatus.APPROVED.value,
                "publication.status": "FAILED",
                "publication.completed_at": failed_at,
                "publication.error_message": str(exc),
                "updated_at": failed_at,
            }},
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        failed_at = datetime.now(timezone.utc)
        await collection.update_one(
            {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
            {"$set": {
                "status": ContentRunStatus.APPROVED.value,
                "publication.status": "FAILED",
                "publication.completed_at": failed_at,
                "publication.error_message": "Unexpected publisher failure",
                "updated_at": failed_at,
            }},
        )
        raise HTTPException(status_code=502, detail="Unexpected publisher failure") from exc

    completed_at = datetime.now(timezone.utc)
    final_update = await collection.update_one(
        {"run_id": run_id, "status": ContentRunStatus.PUBLISHING.value, "publication.attempt_id": attempt_id},
        {"$set": {
            "status": ContentRunStatus.PUBLISHED.value,
            "publication.status": "PUBLISHED",
            "publication.completed_at": completed_at,
            "publication.external_post_urn": result.post_urn,
            "publication.external_image_urn": result.image_urn,
            "updated_at": completed_at,
        }},
    )
    if final_update.matched_count == 0:
        raise HTTPException(
            status_code=500,
            detail="LinkedIn accepted the post but local publication evidence could not be finalized; manual reconciliation required",
        )

    updated = await collection.find_one({"run_id": run_id})
    return _serialize(updated)
