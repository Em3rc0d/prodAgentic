import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from agents.adapters.claim_extractor import ClaimExtractorProtocolError
from agents.adapters.types import ModelExecutionError
from db.mongo import get_db
from models.claim_extractor import (
    ClaimExtractionOutput,
    ClaimExtractionReviewDecision,
    ClaimExtractionReviewRequest,
    ClaimExtractionReviewSnapshot,
    claim_extraction_sha256,
)
from models.content_run import ContentRunStatus


router = APIRouter(tags=["grounding-claim-extractor"])


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/content-runs/{run_id}/grounding/extract-claims")
async def extract_content_run_claims(run_id: str, request: Request):
    """Generate and persist an advisory claim-extraction snapshot.

    Persisting the proposal does not make it complete or authoritative. Any new
    extraction invalidates prior extraction review and downstream Grounding so
    the exact proposed claim map must be explicitly reviewed again.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for claim extraction")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Claim extraction requires READY_FOR_REVIEW content",
        )

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for claim extraction")

    container = getattr(request.app.state, "container", None)
    extractor = getattr(container, "claim_extractor", None)
    if extractor is None:
        raise HTTPException(status_code=503, detail="Claim extractor provider is unavailable")

    content_sha256 = _sha256_text(final_content)
    try:
        extraction = await extractor.extract(
            content=final_content,
            content_sha256=content_sha256,
        )
    except ModelExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Claim extractor provider failed: {exc.category.value}",
        ) from exc
    except ClaimExtractorProtocolError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Claim extractor failed closed: {exc}",
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
                "claim_extraction": extraction.model_dump(mode="python"),
                "claim_extraction_review": None,
                "grounding_assessment": None,
                "grounding_gate": None,
                "grounding_review": None,
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Content run changed while claims were being extracted",
        )

    return extraction.model_dump(mode="json")


@router.post("/content-runs/{run_id}/grounding/claim-extraction/review")
async def review_content_run_claim_extraction(
    run_id: str,
    req: ClaimExtractionReviewRequest,
):
    """Record explicit human completeness review over the exact extraction."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for claim extraction review")

    collection = db["content_runs"]
    existing = await collection.find_one({"run_id": run_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Content run not found")
    if existing.get("status") != ContentRunStatus.READY_FOR_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Claim extraction review requires READY_FOR_REVIEW content",
        )

    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for claim extraction review")

    extraction_doc = existing.get("claim_extraction")
    if not isinstance(extraction_doc, dict):
        raise HTTPException(status_code=409, detail="Current content requires claim extraction")

    try:
        extraction = ClaimExtractionOutput.model_validate(extraction_doc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Stored claim extraction is invalid: {exc}") from exc

    content_sha256 = _sha256_text(final_content)
    if extraction.content_sha256 != content_sha256:
        raise HTTPException(
            status_code=409,
            detail="Claim extraction is stale relative to current final content",
        )

    review = ClaimExtractionReviewSnapshot(
        review_id=str(uuid.uuid4()),
        decision=req.decision,
        extraction_id=extraction.extraction_id,
        content_sha256=content_sha256,
        extraction_sha256=claim_extraction_sha256(extraction),
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
                "claim_extraction_review": review.model_dump(mode="python"),
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Content run changed while claim extraction was being reviewed",
        )

    return review.model_dump(mode="json")


def require_verified_claim_extraction(existing: dict) -> ClaimExtractionOutput:
    """Load the current exact extraction only after explicit completeness review."""
    final_content = existing.get("final_content")
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=409, detail="Final content is not ready for semantic matching")

    extraction_doc = existing.get("claim_extraction")
    review_doc = existing.get("claim_extraction_review")
    if not isinstance(extraction_doc, dict) or not isinstance(review_doc, dict):
        raise HTTPException(
            status_code=409,
            detail="Verified claim extraction is required before semantic matching",
        )

    try:
        extraction = ClaimExtractionOutput.model_validate(extraction_doc)
        review = ClaimExtractionReviewSnapshot.model_validate(review_doc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Stored claim extraction material is invalid: {exc}") from exc

    content_sha256 = _sha256_text(final_content)
    if extraction.content_sha256 != content_sha256:
        raise HTTPException(status_code=409, detail="Claim extraction is stale relative to final content")
    if review.decision != ClaimExtractionReviewDecision.VERIFIED_COMPLETE:
        raise HTTPException(status_code=409, detail="Claim extraction review is not VERIFIED_COMPLETE")
    if review.extraction_id != extraction.extraction_id:
        raise HTTPException(status_code=409, detail="Claim extraction review refers to a different extraction")
    if review.content_sha256 != content_sha256:
        raise HTTPException(status_code=409, detail="Claim extraction review is stale relative to final content")
    if review.extraction_sha256 != claim_extraction_sha256(extraction):
        raise HTTPException(status_code=409, detail="Claim extraction changed after human completeness review")

    return extraction
