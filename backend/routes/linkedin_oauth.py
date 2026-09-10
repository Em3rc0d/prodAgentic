from datetime import datetime, timezone
from urllib.parse import urlencode

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from application.tenancy.context import require_tenant_context
from core.auth import COOKIE_NAME, SessionValidationError
from core.feature_flags import FeatureFlag
from core.linkedin_oauth import (
    LinkedInOAuthConfigurationError,
    LinkedInOAuthError,
    LinkedInOAuthService,
    LinkedInOAuthSettings,
)
from db.mongo import get_db
from infrastructure.linkedin.oauth import S10LinkedInOAuthError, S10LinkedInOAuthService
from infrastructure.mongo.publishing import MongoConnectionRepository


router = APIRouter(prefix="/integrations/linkedin", tags=["integrations"])


def _serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize(item)
            for key, item in value.items()
            if key not in {"encrypted_access_token", "email"}
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _session_id(request: Request) -> str:
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Authentication is not initialized")
    try:
        payload = manager.verify(request.cookies.get(COOKIE_NAME))
    except SessionValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return payload["sid"]


def _db():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return db


def _settings() -> LinkedInOAuthSettings:
    try:
        return LinkedInOAuthSettings.from_env()
    except LinkedInOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _mk1_enabled(request: Request) -> bool:
    registry = getattr(request.app.state, "feature_flags", None)
    return bool(registry and registry.enabled(FeatureFlag.MK1_ENABLED))


def _legacy_service() -> LinkedInOAuthService:
    return LinkedInOAuthService(_db(), settings=_settings())


def _mk1_service(request: Request) -> S10LinkedInOAuthService:
    context = require_tenant_context(request)
    return S10LinkedInOAuthService(_db(), context, settings=_settings())


@router.get("/status")
async def linkedin_connection_status(request: Request):
    if _mk1_enabled(request):
        context = require_tenant_context(request)
        return _serialize(await MongoConnectionRepository(_db(), context).safe_status())
    try:
        return _serialize(await _legacy_service().status())
    except LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/connect")
async def linkedin_connect(request: Request):
    session_id = _session_id(request)
    try:
        service = _mk1_service(request) if _mk1_enabled(request) else _legacy_service()
        authorization_url = await service.create_authorization_url(session_id)
        return {"authorization_url": authorization_url}
    except (LinkedInOAuthError, S10LinkedInOAuthError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/callback")
async def linkedin_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    mk1 = _mk1_enabled(request)
    service = _mk1_service(request) if mk1 else _legacy_service()
    frontend_url = service.settings.frontend_url
    target = "calendar" if mk1 else "publishing"
    if error:
        query = urlencode({"linkedin": "error", "reason": error_description or error})
        return RedirectResponse(f"{frontend_url}/{target}?{query}", status_code=303)

    session_id = _session_id(request)
    try:
        if mk1:
            connection = await service.complete_authorization(
                code=code,
                state=state,
                session_id=session_id,
            )
        else:
            connection = await service.complete_authorization(code, state, session_id)
    except (LinkedInOAuthError, S10LinkedInOAuthError) as exc:
        query = urlencode({"linkedin": "error", "reason": str(exc)})
        return RedirectResponse(f"{frontend_url}/{target}?{query}", status_code=303)

    query = urlencode(
        {"linkedin": "connected", "member": connection.get("display_name") or "LinkedIn member"}
    )
    return RedirectResponse(f"{frontend_url}/{target}?{query}", status_code=303)


@router.post("/disconnect")
async def linkedin_disconnect(request: Request):
    try:
        if _mk1_enabled(request):
            context = require_tenant_context(request)
            await MongoConnectionRepository(_db(), context).disconnect_linkedin(datetime.now(timezone.utc))
        else:
            await _legacy_service().disconnect()
        return {"connected": False, "status": "NOT_CONNECTED"}
    except (LinkedInOAuthError, S10LinkedInOAuthError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
