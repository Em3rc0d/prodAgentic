from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from application.exporting.service import ManualExportAuthorityError, ManualExportService
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.tenants.models import TenantContext
from infrastructure.assets.filesystem import FilesystemAssetStore
from infrastructure.mongo.approval import MongoApprovalRepository
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.rendering import MongoRenderingRepository


router = APIRouter(tags=["mk1-manual-export"])


def _service(request: Request, context: TenantContext) -> ManualExportService:
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_MANUAL_EXPORT):
        raise HTTPException(status_code=404, detail="MK1 Manual Export is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return ManualExportService(
        approval_repository=MongoApprovalRepository(db, context),
        production_repository=MongoProductionRepository(db, context),
        rendering_repository=MongoRenderingRepository(db, context),
        asset_store=FilesystemAssetStore(),
    )


@router.get("/approvals/{approval_id}/manual-export")
async def download_manual_export(
    approval_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        package = await service.build(tenant_id=context.tenant_id, approval_id=approval_id)
    except ManualExportAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    def chunks():
        try:
            while True:
                chunk = package.stream.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            package.stream.close()

    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{package.filename}"',
            "Content-Length": str(package.byte_size),
            "Cache-Control": "private, no-store",
            "X-Approval-SHA256": package.manifest.approval_bundle_sha256,
            "X-Manifest-SHA256": package.manifest_sha256,
            "X-Export-SHA256": package.sha256,
        },
    )
