from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import RevisionStatus
from domain.tenants.models import TenantContext
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.quality import MongoQualityRepository


router = APIRouter(tags=["mk1-quality"])


def _repositories(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_ENABLED):
        raise HTTPException(status_code=404, detail="MK1 quality is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return MongoProductionRepository(db, context), MongoQualityRepository(db, context)


@router.get("/content-revisions/{revision_id}/qa-evidence")
async def get_revision_qa_evidence(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, quality = _repositories(request, context)
    revision = await production.get_revision(context.tenant_id, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="ContentRevision not found")

    try:
        report = await quality.get_latest_report_by_revision(context.tenant_id, revision_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="QA evidence integrity check failed") from exc

    if revision.status == RevisionStatus.REVIEWABLE:
        readiness = "READY_FOR_REVIEW"
    elif report is not None and report.verdict.value == "FAIL":
        readiness = "NEEDS_ATTENTION"
    else:
        readiness = "QA_PENDING"

    return {
        "revision_id": revision.revision_id,
        "revision_status": revision.status.value,
        "readiness": readiness,
        "qa_report": report.model_dump(mode="json") if report is not None else None,
        "approval_available": False,
    }
