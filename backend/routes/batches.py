from dataclasses import replace
import logging
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from application.learning import PerformanceSummaryService, PlannerPerformanceSource
from application.planning import BatchPlannerService, DeterministicCandidateSource, PlanningConflict
from application.planning.formats import AutoFormatCandidateSource, R4_AUTO_FORMAT_POLICY_VERSION
from application.planning.strict import R4StrictBatchPlannerService
from application.tenancy.context import require_tenant_context
from core.demo import demo_mode_enabled
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.planning.models import BatchRequestConstraints, TargetWindow, utc_now
from domain.tenants.models import TenantContext
from infrastructure.mongo.editorial_memory import MongoEditorialMemoryProjector
from infrastructure.mongo.learning import MongoPerformanceEvidenceRepository, MongoPerformanceSummaryRepository
from infrastructure.mongo.recovery import MongoRecoveryRepository
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.profiles import MongoProfileRepository
from infrastructure.planning.model_candidates import CandidateGenerationError, PrecomputedCandidateSource, RouterCandidateSource


router = APIRouter(tags=["mk1-batches"])
logger = logging.getLogger(__name__)

R4_PLANNING_STAGE_SECONDS = 165.0
R4_PLANNING_ATTEMPT_SECONDS = 90.0
R4_PLANNING_FALLBACK_RESERVE_SECONDS = 30.0
R4_PLANNING_MODEL_ROUTES = 3


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
    return registry, db, profiles, planning, projector


def _planning_router(router_instance):
    """Give creative planning its own bounded provider budget without mutating shared authority.

    Real R4.1 UAT exposed both latency-bound and provider-capacity failures for
    the same governed 12-candidate request. Planning is user-triggered and the
    browser request is bounded at 180 seconds, so keep one 165-second stage while
    allowing three known structured-output-capable QUALITY_TEXT model routes.
    With the current allocator the route budget is approximately 90s + 45s + 30s.
    This diversifies model-level capacity without claiming provider independence.
    Shared production-agent routing keeps its stricter two-model default policy.
    """
    planning_router = router_instance.isolated()
    planning_router.policy = replace(
        planning_router.policy,
        max_stage_seconds=R4_PLANNING_STAGE_SECONDS,
        per_attempt_seconds=R4_PLANNING_ATTEMPT_SECONDS,
        minimum_fallback_seconds=R4_PLANNING_FALLBACK_RESERVE_SECONDS,
        max_models_per_stage=R4_PLANNING_MODEL_ROUTES,
    )
    return planning_router


async def _candidate_source_for_request(
    *,
    request: Request,
    context: TenantContext,
    profiles: MongoProfileRepository,
    profile_id: str,
    body: CreateBatchRequest,
):
    if demo_mode_enabled():
        return AutoFormatCandidateSource(DeterministicCandidateSource())

    profile = await profiles.get_profile(profile_id)
    if profile is None or profile.tenant_id != context.tenant_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    version = await profiles.get_version(profile_id, profile.current_version)
    if version is None or version.tenant_id != context.tenant_id:
        raise HTTPException(status_code=409, detail="Current ProfileVersion is unavailable")

    container = getattr(request.app.state, "container", None)
    router_instance = getattr(container, "router", None) if container is not None else None
    if router_instance is None:
        raise HTTPException(status_code=503, detail="Creative planning model router is unavailable")

    target_pool_size = min(BatchPlannerService.candidate_cap, max(8, body.requested_size * 3))
    try:
        candidates = await RouterCandidateSource(_planning_router(router_instance)).generate(
            version,
            body.target_window,
            body.constraints,
            target_pool_size,
        )
    except CandidateGenerationError as exc:
        logger.warning("R4 planning candidate generation failed code=%s", exc.code)
        raise HTTPException(
            status_code=502,
            detail={
                "code": exc.code,
                "message": "Creative planning failed before a valid governed candidate pool was produced",
            },
        ) from exc
    return AutoFormatCandidateSource(PrecomputedCandidateSource(candidates))


@router.post("/profiles/{profile_id}/batches", status_code=201)
async def create_batch(
    profile_id: str,
    body: CreateBatchRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    registry, db, profiles, planning, projector = _repositories(request, context)
    performance_source = None
    if registry.enabled(FeatureFlag.MK1_PLANNER_LEARNING):
        performance_source = PlannerPerformanceSource(
            PerformanceSummaryService(
                evidence=MongoPerformanceEvidenceRepository(db, context),
                summaries=MongoPerformanceSummaryRepository(db, context),
            )
        )

    candidate_source = await _candidate_source_for_request(
        request=request,
        context=context,
        profiles=profiles,
        profile_id=profile_id,
        body=body,
    )
    # R4 API semantics are fail-closed: 201 means the complete requested batch
    # exists and passed batch-level semantic distinctness. Historical S2 direct
    # callers keep BatchPlannerService PARTIAL semantics for compatibility.
    service = R4StrictBatchPlannerService(
        profiles,
        planning,
        candidate_source,
        projector,
        performance_source=performance_source,
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
    except CandidateGenerationError as exc:
        logger.warning("R4 planning candidate binding failed code=%s", exc.code)
        raise HTTPException(
            status_code=502,
            detail={
                "code": exc.code,
                "message": "Candidate pool could not be bound to the planner request",
            },
        ) from exc
    return {
        "batch": _serialize(result.batch.model_dump(mode="json")),
        "content_items": [_serialize(item.model_dump(mode="json")) for item in result.items],
        "plans": [_serialize(item.model_dump(mode="json")) for item in result.plans],
        "planning_trace": _serialize(result.trace.model_dump(mode="json")),
        "memory_count": result.memory_count,
        "creative_source": "deterministic_demo" if demo_mode_enabled() else "model_router",
        "format_policy": R4_AUTO_FORMAT_POLICY_VERSION,
        "completeness_policy": "r4-exact-request-v1",
    }


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _, db, _, planning, _ = _repositories(request, context)
    batch = await planning.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    recovery = MongoRecoveryRepository(db, context)
    _, replacements = await recovery.read(batch_id)
    for entry in replacements:
        await recovery.materialize(planning, entry)
    all_items = await planning.list_batch_items(batch_id)
    replaced_ids = {entry.rejected_content_id for entry in replacements}
    items = [item for item in all_items if item.content_id not in replaced_ids]
    plans = await planning.list_batch_plans(batch_id)
    trace = await planning.get_planning_trace(batch_id)
    if trace is None:
        raise HTTPException(status_code=409, detail="Batch planning trace is unavailable")
    return {
        "batch": _serialize(batch.model_dump(mode="json")),
        "memory_count": len(trace.memory_ids),
        "replacement_lineage": [entry.model_dump(mode="json") for entry in replacements],
        "historical_items": [_serialize(item.model_dump(mode="json")) for item in all_items if item.content_id in replaced_ids],
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
    _, _, profiles, planning, projector = _repositories(request, context)
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
