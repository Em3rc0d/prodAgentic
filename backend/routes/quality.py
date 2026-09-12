from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from application.quality.execution import QualityExecutionError, QualityExecutionService
from application.quality.service import QualityAuthorityError, QualityConflict
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import RevisionStatus
from domain.tenants.models import TenantContext
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.quality import MongoQualityRepository
from infrastructure.mongo.rendering import MongoRenderingRepository
from infrastructure.mongo.visual import MongoVisualRepository
from infrastructure.quality.chromium import ChromiumVisualQAAdapter, VisualInspectorError


router = APIRouter(tags=["mk1-quality"])


def _repositories(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_ENABLED):
        raise HTTPException(status_code=404, detail="MK1 quality is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return (
        MongoProductionRepository(db, context),
        MongoQualityRepository(db, context),
        MongoRenderingRepository(db, context),
        MongoVisualRepository(db, context),
    )


@router.post("/content-revisions/{revision_id}/qa")
async def execute_revision_qa(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, quality, rendering, visual = _repositories(request, context)
    service = QualityExecutionService(
        production_repository=production,
        rendering_repository=rendering,
        visual_repository=visual,
        quality_repository=quality,
        asset_store=FilesystemAssetStore(),
        visual_inspector=ChromiumVisualQAAdapter(),
    )
    try:
        result = await service.execute(tenant_id=context.tenant_id, revision_id=revision_id)
    except VisualInspectorError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QualityExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QualityAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QualityConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    authority = result.authority
    return {
        "revision": authority.revision.model_dump(mode="json"),
        "run": authority.run.model_dump(mode="json"),
        "qa_report": authority.report.model_dump(mode="json"),
        "reviewable": authority.reviewable,
        "recovery": result.recovery.model_dump(mode="json"),
        "next_stage": "S7_REVIEW" if authority.reviewable else "S6_ATTENTION",
    }


@router.get("/content-revisions/{revision_id}/qa-evidence")
async def get_revision_qa_evidence(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, quality, _, _ = _repositories(request, context)
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
