from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from application.approval.service import ApprovalAuthorityError, ApprovalConflict, ApprovalService
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import ContentSpecV1
from domain.tenants.models import TenantContext
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.mongo.approval import MongoApprovalRepository
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.profiles import MongoProfileRepository
from infrastructure.mongo.quality import MongoQualityRepository
from infrastructure.mongo.rendering import MongoRenderingRepository
from infrastructure.mongo.visual import MongoVisualRepository


router = APIRouter(tags=["mk1-review-approval"])


class ApproveRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class HumanEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    edited_content: ContentSpecV1


def _service(request: Request, context: TenantContext) -> ApprovalService:
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_REVIEW_APPROVAL):
        raise HTTPException(status_code=404, detail="MK1 Review + Approval V2 is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return ApprovalService(
        planning_repository=MongoPlanningRepository(db, context),
        profile_repository=MongoProfileRepository(db, context),
        production_repository=MongoProductionRepository(db, context),
        visual_repository=MongoVisualRepository(db, context),
        rendering_repository=MongoRenderingRepository(db, context),
        quality_repository=MongoQualityRepository(db, context),
        approval_repository=MongoApprovalRepository(db, context),
        asset_store=FilesystemAssetStore(),
    )


@router.get("/content-revisions/{revision_id}/review-authority")
async def get_review_authority(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        snapshot = await service.review_snapshot(tenant_id=context.tenant_id, revision_id=revision_id)
    except ApprovalConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApprovalAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return snapshot.model_dump(mode="json")


@router.post("/content-revisions/{revision_id}/approve", status_code=201)
async def approve_revision(
    revision_id: str,
    body: ApproveRevisionRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        bundle = await service.approve(
            tenant_id=context.tenant_id,
            revision_id=revision_id,
            expected_review_digest=body.expected_review_digest,
            approved_by=context.actor_id,
        )
    except ApprovalConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApprovalAuthorityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"approval": bundle.model_dump(mode="json"), "next_stage": "S8_EXPORT_PACKAGE"}


@router.post("/content-revisions/{revision_id}/edit", status_code=201)
async def edit_revision(
    revision_id: str,
    body: HumanEditRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        result = await service.fork_human_edit(
            tenant_id=context.tenant_id,
            revision_id=revision_id,
            expected_review_digest=body.expected_review_digest,
            edited_content=body.edited_content,
        )
    except ApprovalConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApprovalAuthorityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "revision": result.revision.model_dump(mode="json"),
        "run": result.run.model_dump(mode="json"),
        "visual_reused": result.visual_reused,
        "invalidated": result.invalidated,
        "next_stage": "S4_OR_S5_BY_INVALIDATION_FRONTIER",
    }
