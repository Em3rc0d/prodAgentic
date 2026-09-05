from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from application.planning import BatchPlannerService, DeterministicCandidateSource, PlanningConflict
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.planning.models import BatchRequestConstraints, TargetWindow, utc_now
from domain.tenants.models import TenantContext
from infrastructure.mongo.editorial_memory import MongoEditorialMemoryProjector
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.profiles import MongoProfileRepository


router = APIRouter(tags=["mk1-batches"])


class CreateBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_window: TargetWindow
    requested_size: int = Field(ge=1, le=30)
    constraints: BatchRequestConstraints = Field(default_factory=BatchRequestConstraints)


def _serialize(value):
    if isinstance(value, (ObjectId, datetime)):
        return str(value) if isinstance(value, ObjectId) else value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _repositories(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_BATCH_PLANNING):
        raise HTTPException(status_code=404, detail="Batch planning is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    planning = MongoPlanningRepository(db, context)
    profiles = MongoProfileRepository(db, context)
    projector = MongoEditorialMemoryProjector(db, context, planning)
    return profiles, planning, projector


@router.post("/profiles/{profile_id}/batches", status_code=201)
async def create_batch(
    profile_id: str,
    body: CreateBatchRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    profiles, planning, projector = _repositories(request, context)
    service = BatchPlannerService(
        profiles,
        planning,
        DeterministicCandidateSource(),
        projector,
    )
    try:
        result = await service.create_batch(
            context.tenant_id,
            profile_id,
            body.target_window,
            body.requested_size,
            body.constraints,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlanningConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "batch": _serialize(result.batch.model_dump(mode="json")),
        "content_items": [_serialize(item.model_dump(mode="json")) for item in result.items],
        "plans": [_serialize(item.model_dump(mode="json")) for item in result.plans],
        "planning_trace": _serialize(result.trace.model_dump(mode="json")),
        "memory_count": result.memory_count,
    }


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _, planning, _ = _repositories(request, context)
    batch = await planning.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    items = await planning.list_batch_items(batch_id)
    plans = await planning.list_batch_plans(batch_id)
    trace = await planning.get_planning_trace(batch_id)
    if trace is None:
        raise HTTPException(status_code=409, detail="Batch planning trace is unavailable")
    return {
        "batch": _serialize(batch.model_dump(mode="json")),
        "content_items": [_serialize(item.model_dump(mode="json")) for item in items],
        "plans": [_serialize(item.model_dump(mode="json")) for item in plans],
        "planning_trace": _serialize(trace.model_dump(mode="json")),
    }


@router.get("/profiles/{profile_id}/editorial-memory")
async def get_editorial_memory(
    profile_id: str,
    request: Request,
    days: int = 30,
    context: TenantContext = Depends(require_tenant_context),
):
    profiles, planning, projector = _repositories(request, context)
    profile = await profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if days < 7 or days > 180:
        raise HTTPException(status_code=422, detail="days must be between 7 and 180")
    now = utc_now()
    await projector.refresh(profile_id, now)
    entries = await planning.list_recent_memory(profile_id, now - timedelta(days=days))
    return {
        "entries": [_serialize(item.model_dump(mode="json")) for item in entries],
        "count": len(entries),
    }
