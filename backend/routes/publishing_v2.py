from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from application.publishing.reconciliation import ReconciliationService
from application.publishing.service import (
    CalendarService,
    PublishingAuthorityError,
    PublishingConflict,
    PublishingUnavailable,
    SchedulingService,
)
from application.tenancy.context import require_tenant_context
from core.auth import COOKIE_NAME, SessionValidationError
from core.feature_flags import FeatureFlag
from core.linkedin_oauth import LinkedInOAuthConfigurationError, LinkedInOAuthSettings
from db.mongo import get_db
from domain.publishing.models import ScheduleState
from domain.tenants.models import TenantContext
from infrastructure.linkedin.adapter import LinkedInPlatformAdapter
from infrastructure.linkedin.oauth import S10LinkedInOAuthError, S10LinkedInOAuthService
from infrastructure.mongo.approval import MongoApprovalRepository
from infrastructure.mongo.approval_calendar import MongoApprovalCalendarReader
from infrastructure.mongo.publishing import (
    MongoConnectionRepository,
    MongoPublicationRepository,
    MongoScheduleRepository,
)


router = APIRouter(tags=["mk1-calendar-publishing"])


class CreateScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheduled_for: datetime
    timezone_context: str = Field(min_length=1, max_length=120)
    destination: str = Field(default="member_feed", min_length=1, max_length=120)


def _db():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return db


def _flags(request: Request):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_ENABLED):
        raise HTTPException(status_code=404, detail="MK1 publishing surfaces are not enabled")
    return registry


def _automatic_enabled(request: Request) -> bool:
    registry = _flags(request)
    return registry.enabled(FeatureFlag.MK1_PUBLISH_WORKER) and registry.enabled(
        FeatureFlag.MK1_REDIS_TRANSPORT
    )


def _require_automatic(request: Request) -> None:
    if not _automatic_enabled(request):
        raise HTTPException(
            status_code=409,
            detail="Automatic publishing is disabled; Manual Export remains available",
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


def _repos(context: TenantContext):
    db = _db()
    return (
        MongoScheduleRepository(db, context),
        MongoPublicationRepository(db, context),
        MongoConnectionRepository(db, context),
    )


@router.get("/connections/linkedin/status")
async def connection_status(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    _, _, connections = _repos(context)
    safe = await connections.safe_status()
    connection = await connections.get_linkedin()
    capability = await LinkedInPlatformAdapter().capabilities(connection) if connection else None
    return {
        **safe,
        "capability": capability.model_dump(mode="json") if capability else None,
    }


@router.post("/connections/linkedin/connect")
async def connection_connect(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    try:
        service = S10LinkedInOAuthService(_db(), context, settings=_settings())
        authorization_url = await service.create_authorization_url(_session_id(request))
        return {"authorization_url": authorization_url}
    except S10LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/connections/linkedin")
async def connection_disconnect(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    _, _, connections = _repos(context)
    await connections.disconnect_linkedin(datetime.now(timezone.utc))
    return {"provider": "linkedin", "connected": False, "status": "NOT_CONNECTED"}


@router.post("/approvals/{approval_id}/schedules", status_code=201)
async def create_schedule(
    approval_id: str,
    body: CreateScheduleRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _require_automatic(request)
    schedules, _, connections = _repos(context)
    service = SchedulingService(
        approvals=MongoApprovalRepository(_db(), context),
        schedules=schedules,
        connections=connections,
        adapter=LinkedInPlatformAdapter(),
    )
    try:
        result = await service.schedule_linkedin(
            tenant_id=context.tenant_id,
            approval_id=approval_id,
            scheduled_for=body.scheduled_for,
            timezone_context=body.timezone_context,
            destination=body.destination,
        )
    except PublishingUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PublishingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PublishingAuthorityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "schedule": result.schedule.model_dump(mode="json"),
        "capability": result.capability.model_dump(mode="json"),
    }


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    schedules, _, _ = _repos(context)
    schedule = await schedules.get(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule.model_dump(mode="json")


@router.delete("/schedules/{schedule_id}")
async def cancel_schedule(
    schedule_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    schedules, _, _ = _repos(context)
    current = await schedules.get(schedule_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if current.state is not ScheduleState.SCHEDULED:
        raise HTTPException(status_code=409, detail="Only a not-yet-dispatched schedule can be cancelled")
    cancelled = await schedules.cancel(schedule_id, datetime.now(timezone.utc))
    if cancelled is None or cancelled.state is not ScheduleState.CANCELLED:
        raise HTTPException(status_code=409, detail="Schedule changed before cancellation")
    return cancelled.model_dump(mode="json")


@router.get("/publications/{publication_id}")
async def get_publication(
    publication_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    _, publications, _ = _repos(context)
    publication = await publications.get(publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return publication.model_dump(mode="json")


@router.post("/publications/{publication_id}/reconcile")
async def reconcile_publication(
    publication_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    _flags(request)
    schedules, publications, connections = _repos(context)
    service = ReconciliationService(
        publications=publications,
        schedules=schedules,
        connections=connections,
        adapter=LinkedInPlatformAdapter(),
    )
    try:
        publication = await service.reconcile(publication_id)
    except PublishingAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return publication.model_dump(mode="json")


@router.get("/calendar")
async def calendar_view(
    request: Request,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    context: TenantContext = Depends(require_tenant_context),
):
    automatic = _automatic_enabled(request)
    now = datetime.now(timezone.utc)
    start = start_at or (now - timedelta(days=7))
    end = end_at or (now + timedelta(days=35))
    schedules, publications, connections = _repos(context)
    service = CalendarService(
        schedules=schedules,
        publications=publications,
        connections=connections,
        adapter=LinkedInPlatformAdapter(),
        approval_reader=MongoApprovalCalendarReader(_db(), context),
        automatic_enabled=automatic,
    )
    try:
        return await service.view(start_at=start, end_at=end)
    except PublishingConflict as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
