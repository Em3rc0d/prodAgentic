from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from application.tenancy.context import require_tenant_context
from application.visual.planner import UnsupportedVisualFormat
from application.visual.service import VisualAuthorityError, VisualPlanningConflict, VisualSpecService
from application.visual.validation import VisualSpecValidationError
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.tenants.models import TenantContext
from domain.visual.models import canonical_visual_sha256
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.profiles import MongoProfileRepository
from infrastructure.mongo.visual import MongoVisualRepository


router = APIRouter(tags=["mk1-visual"])


def _repositories(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_VISUALSPEC):
        raise HTTPException(status_code=404, detail="VisualSpec V1 is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return (
        MongoProductionRepository(db, context),
        MongoProfileRepository(db, context),
        MongoVisualRepository(db, context),
    )


@router.post("/content-revisions/{revision_id}/visual-spec", status_code=201)
async def create_visual_spec(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, profiles, visual = _repositories(request, context)
    service = VisualSpecService(
        production_repository=production,
        profile_repository=profiles,
        visual_repository=visual,
    )
    try:
        result = await service.plan_revision(tenant_id=context.tenant_id, revision_id=revision_id)
    except VisualAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VisualPlanningConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnsupportedVisualFormat as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VisualSpecValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Visual planning failed before a valid VisualSpecV1 was accepted",
        ) from exc

    return {
        "run": result.run.model_dump(mode="json"),
        "revision": result.revision.model_dump(mode="json"),
        "design_profile": result.design_profile.model_dump(mode="json"),
        "visual_spec": result.visual_spec.model_dump(mode="json"),
        "visual_spec_digest": result.visual_spec_digest,
        "next_stage": "S5_RENDERER",
    }


@router.get("/visual-specs/{visual_spec_id}")
async def get_visual_spec(
    visual_spec_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _, _, visual = _repositories(request, context)
    try:
        spec = await visual.get_visual_spec(visual_spec_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="VisualSpec integrity check failed") from exc
    if spec is None:
        raise HTTPException(status_code=404, detail="VisualSpec not found")

    try:
        design_profile = await visual.get_design_profile(spec.style.design_profile_ref)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="DesignProfile integrity check failed") from exc
    if design_profile is None or design_profile.digest != spec.style.design_profile_digest:
        raise HTTPException(status_code=409, detail="VisualSpec DesignProfile lineage is unavailable")

    return {
        "visual_spec": spec.model_dump(mode="json"),
        "visual_spec_digest": canonical_visual_sha256(spec),
        "design_profile": design_profile.model_dump(mode="json"),
    }
