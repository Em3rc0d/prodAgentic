from datetime import datetime
from urllib.parse import urlencode

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from core.auth import COOKIE_NAME, SessionValidationError
from core.linkedin_oauth import (
    LinkedInOAuthConfigurationError,
    LinkedInOAuthError,
    LinkedInOAuthService,
    LinkedInOAuthSettings,
)
from db.mongo import get_db


router = APIRouter(prefix="/integrations/linkedin", tags=["integrations"])


def _serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items() if key not in {"encrypted_access_token", "email"}}
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


def _service() -> LinkedInOAuthService:
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    try:
        settings = LinkedInOAuthSettings.from_env()
    except LinkedInOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LinkedInOAuthService(db, settings=settings)


@router.get("/status")
async def linkedin_connection_status():
    try:
        return _serialize(await _service().status())
    except HTTPException:
        raise
    except LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/connect")
async def linkedin_connect(request: Request):
    session_id = _session_id(request)
    try:
        authorization_url = await _service().create_authorization_url(session_id)
        return {"authorization_url": authorization_url}
    except LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/callback")
async def linkedin_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    service = _service()
    frontend_url = service.settings.frontend_url
    if error:
        query = urlencode({"linkedin": "error", "reason": error_description or error})
        return RedirectResponse(f"{frontend_url}/publishing?{query}", status_code=303)

    session_id = _session_id(request)
    try:
        connection = await service.complete_authorization(code, state, session_id)
    except LinkedInOAuthError as exc:
        query = urlencode({"linkedin": "error", "reason": str(exc)})
        return RedirectResponse(f"{frontend_url}/publishing?{query}", status_code=303)

    query = urlencode({"linkedin": "connected", "member": connection.get("display_name") or "LinkedIn member"})
    return RedirectResponse(f"{frontend_url}/publishing?{query}", status_code=303)


@router.post("/disconnect")
async def linkedin_disconnect():
    try:
        await _service().disconnect()
        return {"connected": False, "status": "NOT_CONNECTED"}
    except LinkedInOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
