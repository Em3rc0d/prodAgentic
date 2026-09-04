from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from application.profiles import DeterministicProfileAnalyzer, ProfileConflict, ProfileService
from application.profiles.service import ProposalMismatch
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.profiles.models import ProfileSetup
from domain.tenants.models import TenantContext
from infrastructure.mongo.profiles import MongoProfileRepository


router = APIRouter(tags=["mk1-profiles"])


class AcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    setup: ProfileSetup
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class UpdateAcceptanceRequest(AcceptanceRequest):
    expected_current_version: int = Field(ge=1)


def _serialize(value):
    if isinstance(value, (ObjectId, datetime)):
        return str(value) if isinstance(value, ObjectId) else value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _service(request: Request, context: TenantContext) -> ProfileService:
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_PROFILE_V2):
        raise HTTPException(status_code=404, detail="Profile V2 is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return ProfileService(MongoProfileRepository(db, context), DeterministicProfileAnalyzer())


@router.post("/profiles/inference-proposals")
async def propose_profile(
    setup: ProfileSetup,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    return _serialize(_service(request, context).propose(setup).model_dump(mode="json"))


@router.get("/profiles")
async def list_profiles(
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    profiles = await _service(request, context).repository.list_profiles()
    return {"profiles": [_serialize(profile.model_dump(mode="json")) for profile in profiles], "count": len(profiles)}


@router.post("/profiles", status_code=201)
async def create_profile(
    body: AcceptanceRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    try:
        accepted = await _service(request, context).create(context.tenant_id, body.setup, body.proposal_digest)
    except ProposalMismatch as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "profile": _serialize(accepted.profile.model_dump(mode="json")),
        "version": _serialize(accepted.version.model_dump(mode="json")),
    }


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    profile = await service.repository.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    version = await service.repository.get_version(profile_id, profile.current_version)
    if version is None:
        raise HTTPException(status_code=409, detail="Current ProfileVersion is unavailable")
    return {
        "profile": _serialize(profile.model_dump(mode="json")),
        "version": _serialize(version.model_dump(mode="json")),
    }


@router.get("/profiles/{profile_id}/versions/{version}")
async def get_profile_version(
    profile_id: str,
    version: int,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    item = await _service(request, context).repository.get_version(profile_id, version)
    if item is None:
        raise HTTPException(status_code=404, detail="ProfileVersion not found")
    return _serialize(item.model_dump(mode="json"))


@router.post("/profiles/{profile_id}/versions")
async def update_profile(
    profile_id: str,
    body: UpdateAcceptanceRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    try:
        accepted = await _service(request, context).update(
            context.tenant_id,
            profile_id,
            body.expected_current_version,
            body.setup,
            body.proposal_digest,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ProfileConflict, ProposalMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "profile": _serialize(accepted.profile.model_dump(mode="json")),
        "version": _serialize(accepted.version.model_dump(mode="json")),
    }
