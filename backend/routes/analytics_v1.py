from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from application.analytics.jobs import AnalyticsJobEnqueuer
from application.analytics.service import (
    AnalyticsAuthorityError,
    AnalyticsIntentPlanner,
    AnalyticsReadService,
    AnalyticsUnavailable,
)
from application.learning import PerformanceSummaryService
from application.tenancy.context import require_tenant_context
from core.auth import COOKIE_NAME, SessionValidationError
from core.feature_flags import FeatureFlag
from core.linkedin_oauth import LinkedInOAuthConfigurationError, LinkedInOAuthSettings
from db.mongo import get_db
from domain.tenants.models import TenantContext
from infrastructure.linkedin.analytics import LinkedInAnalyticsAdapter
from infrastructure.linkedin.oauth import S10LinkedInOAuthError, S10LinkedInOAuthService
from infrastructure.mongo.analytics import MongoMetricSnapshotRepository
from infrastructure.mongo.analytics_jobs import MongoAnalyticsJobOutboxRepository
from infrastructure.mongo.analytics_publications import MongoPublishedPublicationAnalyticsReader
from infrastructure.mongo.learning import MongoPerformanceEvidenceRepository, MongoPerformanceSummaryRepository
from infrastructure.mongo.publishing import MongoConnectionRepository


router = APIRouter(tags=["mk1-analytics"])


def _db():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return db


def _flags(request: Request):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_ENABLED):
        raise HTTPException(status_code=404, detail="MK1 analytics surfaces are not enabled")
    return registry


def _automatic_enabled(request: Request) -> bool:
    registry = _flags(request)
    return registry.enabled(FeatureFlag.MK1_ANALYTICS_WORKER) and registry.enabled(
        FeatureFlag.MK1_REDIS_TRANSPORT
    )


def _settings() -> LinkedInOAuthSettings:
    try:
        return LinkedInOAuthSettings.from_env()
    except LinkedInOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _session_id(request: Request) -> str:
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Authentication is not initialized")
    try:
        payload = manager.verify(request.cookies.get(COOKIE_NAME))
    except SessionValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return payload["sid"]


def _components(context: TenantContext):
    db = _db()
    publications = MongoPublishedPublicationAnalyticsReader(db, context)
    connections = MongoConnectionRepository(db, context)
    snapshots = MongoMetricSnapshotRepository(db, context)
    adapter = LinkedInAnalyticsAdapter()
    return db, publications, connections, snapshots, adapter


def _learning_components(context: TenantContext):
    db = _db()
    summaries = MongoPerformanceSummaryRepository(db, context)
    service = PerformanceSummaryService(
        evidence=MongoPerformanceEvidenceRepository(db, context),
        summaries=summaries,
    )
    return summaries, service


@router.get("/analytics/overview")
async def analytics_overview(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    _, publications, connections, snapshots, adapter = _components(context)
    service = AnalyticsReadService(
        publications=publications,
        connections=connections,
        snapshots=snapshots,
        adapter=adapter,
    )
    payload = await service.overview()
    recent = await snapshots.list_recent(limit=250)
    latest_by_publication = {}
    for snapshot in recent:
        latest_by_publication.setdefault(snapshot.publication_id, snapshot)
        if len(latest_by_publication) >= 25:
            break
    payload["latest_snapshots"] = [
        snapshot.model_dump(mode="json") for snapshot in latest_by_publication.values()
    ]
    payload["automatic_collection_enabled"] = _automatic_enabled(request)
    return payload


@router.get("/analytics/performance-summary")
async def performance_summary(
    request: Request,
    profile_id: str = Query(min_length=1, max_length=128),
    context: TenantContext = Depends(require_tenant_context),
):
    registry = _flags(request)
    summaries, _ = _learning_components(context)
    summary = await summaries.latest_for_profile(profile_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Performance summary not built for this profile")
    return {
        "summary": summary.model_dump(mode="json"),
        "planner_learning_enabled": registry.enabled(FeatureFlag.MK1_PLANNER_LEARNING),
        "interpretation": "observational_association_not_causality",
    }


@router.post("/analytics/performance-summary/rebuild")
async def rebuild_performance_summary(
    request: Request,
    profile_id: str = Query(min_length=1, max_length=128),
    context: TenantContext = Depends(require_tenant_context),
):
    registry = _flags(request)
    _, service = _learning_components(context)
    try:
        summary = await service.rebuild(profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "summary": summary.model_dump(mode="json"),
        "planner_learning_enabled": registry.enabled(FeatureFlag.MK1_PLANNER_LEARNING),
        "interpretation": "observational_association_not_causality",
    }


@router.get("/analytics/publications/{publication_id}/snapshots")
async def publication_snapshots(
    publication_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    _, publications, connections, snapshots, adapter = _components(context)
    service = AnalyticsReadService(
        publications=publications,
        connections=connections,
        snapshots=snapshots,
        adapter=adapter,
    )
    try:
        items = await service.publication_snapshots(publication_id, limit=limit)
    except AnalyticsAuthorityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"publication_id": publication_id, "snapshots": [item.model_dump(mode="json") for item in items]}


@router.post("/analytics/publications/{publication_id}/collect")
async def collect_publication_analytics(
    publication_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    if not _automatic_enabled(request):
        raise HTTPException(
            status_code=409,
            detail="Automatic analytics collection is disabled",
        )
    db, publications, connections, snapshots, adapter = _components(context)
    jobs = AnalyticsJobEnqueuer(MongoAnalyticsJobOutboxRepository(db))
    planner = AnalyticsIntentPlanner(
        publications=publications,
        connections=connections,
        snapshots=snapshots,
        adapter=adapter,
        jobs=jobs,
    )
    try:
        result = await planner.enqueue_manual(publication_id=publication_id)
    except AnalyticsUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AnalyticsAuthorityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "publication_id": result.publication_id,
        "collection_bucket": result.collection_bucket,
        "operation_key": result.operation_key,
        "status": "QUEUED",
    }


@router.post("/connections/linkedin/analytics/enable")
async def enable_linkedin_analytics(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    try:
        service = S10LinkedInOAuthService(_db(), context, settings=_settings())
        authorization_url = await service.create_authorization_url(
            _session_id(request),
            extra_scopes=(LinkedInAnalyticsAdapter.REQUIRED_SCOPE,),
        )
    except S10LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "authorization_url": authorization_url,
        "requested_scope": LinkedInAnalyticsAdapter.REQUIRED_SCOPE,
    }
