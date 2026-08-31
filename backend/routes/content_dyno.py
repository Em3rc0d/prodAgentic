from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from core.content_dyno import ContentDynoAnalyzer
from db.mongo import get_db
from models.content_dyno import HumanEditorialReview, HumanEditorialReviewInput
from models.content_run import ContentRun, ContentRunStatus


router = APIRouter(tags=["content-dyno"])


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _current_review_identity(existing: dict) -> tuple[str, str]:
    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(
            status_code=409,
            detail="Final content is required before editorial dyno review",
        )

    visual = existing.get("visual_render")
    if not isinstance(visual, dict) or visual.get("status") != "READY":
        raise HTTPException(
            status_code=409,
            detail="A READY final visual is required before editorial dyno review",
        )
    visual_sha256 = visual.get("asset_sha256")
    if (
        not isinstance(visual_sha256, str)
        or len(visual_sha256) != 64
        or any(character not in "0123456789abcdef" for character in visual_sha256)
    ):
        raise HTTPException(
            status_code=409,
            detail="Final visual is missing valid immutable SHA-256 evidence",
        )

    return _sha256_text(final_content), visual_sha256


@router.post("/content-runs/{run_id}/dyno/review")
async def submit_content_dyno_review(run_id: str, req: HumanEditorialReviewInput):
    """Persist explicit human editorial judgement with server-owned identity.

    The client may submit subjective scores, verdict and notes only. The server
    binds that judgement to the exact current ContentRun text and visual asset.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for content dyno")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Editorial dyno review requires READY_FOR_REVIEW content",
        )

    content_sha256, visual_sha256 = _current_review_identity(existing)
    review = HumanEditorialReview(
        run_id=run_id,
        final_content_sha256=content_sha256,
        visual_asset_sha256=visual_sha256,
        **req.model_dump(mode="python"),
    )
    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {
            "run_id": run_id,
            "status": ContentRunStatus.READY_FOR_REVIEW.value,
            "updated_at": existing.get("updated_at"),
        },
        {
            "$set": {
                "content_dyno_review": review.model_dump(mode="python"),
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Content run changed while editorial dyno review was being saved",
        )

    return review.model_dump(mode="json")


@router.get("/content-runs/{run_id}/dyno")
async def get_content_dyno_report(run_id: str):
    """Measure the current final asset using persisted human judgement if any."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for content dyno")

    existing = await db["content_runs"].find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")

    try:
        run = ContentRun.model_validate(existing)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Stored ContentRun is invalid for content dyno: {exc}",
        ) from exc

    report = ContentDynoAnalyzer.analyze(run, run.content_dyno_review)
    return report.model_dump(mode="json")
