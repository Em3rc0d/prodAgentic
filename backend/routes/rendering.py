from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from application.rendering.copy_resolver import UnsupportedRenderInput
from application.rendering.service import (
    RenderAuthorityError,
    RenderConflict,
    RenderExecutionFailed,
    RenderIntegrityError,
    RenderService,
)
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import RevisionStatus
from domain.tenants.models import TenantContext
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.rendering import MongoRenderingRepository
from infrastructure.mongo.visual import MongoVisualRepository
from infrastructure.rendering.chromium import ChromiumRendererAdapter


router = APIRouter(tags=["mk1-rendering"])


def _runtime(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if (
        registry is None
        or not registry.enabled(FeatureFlag.MK1_VISUALSPEC)
        or not registry.enabled(FeatureFlag.MK1_RENDER_WORKER)
    ):
        raise HTTPException(status_code=404, detail="MK1 Renderer + AssetStore is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    production = MongoProductionRepository(db, context)
    visual = MongoVisualRepository(db, context)
    rendering = MongoRenderingRepository(db, context)
    asset_store = FilesystemAssetStore()
    renderer = ChromiumRendererAdapter()
    return production, visual, rendering, asset_store, renderer


@router.post("/content-revisions/{revision_id}/render", status_code=201)
async def render_revision(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, visual, rendering, asset_store, renderer = _runtime(request, context)
    service = RenderService(
        production_repository=production,
        visual_repository=visual,
        rendering_repository=rendering,
        renderer=renderer,
        asset_store=asset_store,
    )
    try:
        result = await service.render_revision(tenant_id=context.tenant_id, revision_id=revision_id)
    except RenderAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RenderConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RenderIntegrityError as exc:
        raise HTTPException(status_code=409, detail="S5 render integrity check failed") from exc
    except UnsupportedRenderInput as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RenderExecutionFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "run": result.run.model_dump(mode="json"),
        "revision": result.revision.model_dump(mode="json"),
        "render_result": result.render_result.model_dump(mode="json"),
        "preview": _preview_payload(result.revision, result.render_result),
        "next_stage": "S6_QA",
    }


@router.get("/render-results/{render_id}")
async def get_render_result(
    render_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _, _, rendering, asset_store, _ = _runtime(request, context)
    try:
        result = await rendering.get_render_result(render_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="RenderResult integrity check failed") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="RenderResult not found")
    for asset in result.assets:
        if not await asset_store.verify(asset.storage_key, asset.sha256):
            raise HTTPException(status_code=409, detail="RenderResult owned asset hash check failed")
    return {"render_result": result.model_dump(mode="json")}


@router.get("/render-assets/{asset_id}/content")
async def get_render_asset_content(
    asset_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _, _, rendering, asset_store, _ = _runtime(request, context)
    try:
        asset = await rendering.get_asset(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Asset metadata integrity check failed") from exc
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not await asset_store.verify(asset.storage_key, asset.sha256):
        raise HTTPException(status_code=409, detail="Owned asset hash check failed")
    data = await asset_store.get(asset.storage_key)
    return Response(
        content=data,
        media_type=asset.content_type.value,
        headers={
            "ETag": f'"{asset.sha256}"',
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/content-revisions/{revision_id}/render-preview")
async def get_render_preview(
    revision_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    production, visual, rendering, asset_store, _ = _runtime(request, context)
    revision = await production.get_revision(context.tenant_id, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="ContentRevision not found")
    if revision.status not in {RevisionStatus.QA_PENDING, RevisionStatus.REVIEWABLE} or not revision.asset_refs:
        raise HTTPException(status_code=409, detail="Revision does not own a complete rendered asset set")
    if revision.visual_spec_ref is None:
        raise HTTPException(status_code=409, detail="Revision VisualSpec lineage is unavailable")
    visual_spec = await visual.get_visual_spec(revision.visual_spec_ref)
    if visual_spec is None:
        raise HTTPException(status_code=409, detail="Revision VisualSpec lineage is unavailable")

    assets = []
    for asset_id in revision.asset_refs:
        asset = await rendering.get_asset(asset_id)
        if asset is None or asset.revision_id != revision.revision_id or asset.visual_spec_id != visual_spec.visual_spec_id:
            raise HTTPException(status_code=409, detail="Revision asset lineage is incomplete")
        if not await asset_store.verify(asset.storage_key, asset.sha256):
            raise HTTPException(status_code=409, detail="Revision owned asset hash check failed")
        assets.append(asset)
    assets.sort(key=lambda item: item.page_index)
    if len(assets) != len(visual_spec.pages):
        raise HTTPException(status_code=409, detail="Revision render page count is incomplete")

    return {
        "revision_id": revision.revision_id,
        "status": revision.status.value,
        "qa_state": revision.status.value,
        "format": visual_spec.format.value,
        "alt_text": visual_spec.alt_text_plan,
        "assets": [
            {
                "asset_id": asset.asset_id,
                "page_id": asset.page_id,
                "page_index": asset.page_index,
                "width": asset.width,
                "height": asset.height,
                "sha256": asset.sha256,
                "url": f"/api/render-assets/{asset.asset_id}/content",
            }
            for asset in assets
        ],
    }


def _preview_payload(revision, result):
    return {
        "revision_id": revision.revision_id,
        "status": revision.status.value,
        "qa_state": revision.status.value,
        "assets": [
            {
                "asset_id": asset.asset_id,
                "page_id": asset.page_id,
                "page_index": asset.page_index,
                "width": asset.width,
                "height": asset.height,
                "sha256": asset.sha256,
                "url": f"/api/render-assets/{asset.asset_id}/content",
            }
            for asset in result.assets
        ],
    }
