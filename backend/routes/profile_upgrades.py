from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from application.profiles.patch_service import ProfilePatchNoop, ProfilePatchService
from application.profiles.service import ProfileConflict
from application.profiles.upgrade_service import (
    ProfileUpgradeConflict,
    ProfileUpgradeService,
    ProfileUpgradeStale,
)
from application.tenancy.context import require_tenant_context
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.profiles.upgrades import ProfileUpgradeDecisionValue
from domain.tenants.models import TenantContext
from infrastructure.mongo.profile_upgrades import (
    MongoProfileUpgradeDecisionRepository,
    ProfileUpgradeDecisionConflict,
)
from infrastructure.mongo.profiles import MongoProfileRepository


router = APIRouter(tags=["mk1-profile-upgrades"])


class ProfileUpgradeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ProfileUpgradeDecisionValue
    expected_current_version: int = Field(ge=1)
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def _serialize(value):
    if isinstance(value, (ObjectId, datetime)):
        return str(value) if isinstance(value, ObjectId) else value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _service(request: Request, context: TenantContext) -> ProfileUpgradeService:
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_PROFILE_V2):
        raise HTTPException(status_code=404, detail="Profile V2 is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    profiles = MongoProfileRepository(db, context)
    return ProfileUpgradeService(
        profiles=profiles,
        decisions=MongoProfileUpgradeDecisionRepository(db, context),
        profile_patches=ProfilePatchService(profiles),
    )


@router.get("/profiles/{profile_id}/upgrade-proposal")
async def get_profile_upgrade_proposal(
    profile_id: str,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        proposal = await service.propose(profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileUpgradeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if proposal is None:
        return {"profile_id": profile_id, "eligible": False, "proposal": None, "decision": None}
    decision = await service.decision_for(proposal.proposal_id)
    return {
        "profile_id": profile_id,
        "eligible": True,
        "proposal": _serialize(proposal.model_dump(mode="json")),
        "decision": _serialize(decision.model_dump(mode="json")) if decision is not None else None,
        "authority": "proposal_only_until_human_decision",
    }


@router.post("/profiles/{profile_id}/upgrade-proposal/decision")
async def decide_profile_upgrade(
    profile_id: str,
    body: ProfileUpgradeDecisionRequest,
    request: Request,
    context: TenantContext = Depends(require_tenant_context),
):
    service = _service(request, context)
    try:
        result = await service.decide(
            tenant_id=context.tenant_id,
            profile_id=profile_id,
            proposal_digest=body.proposal_digest,
            expected_current_version=body.expected_current_version,
            decision=body.decision,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ProfileUpgradeConflict,
        ProfileUpgradeStale,
        ProfileUpgradeDecisionConflict,
        ProfileConflict,
        ProfilePatchNoop,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    payload = {
        "decision": _serialize(result.decision.model_dump(mode="json")),
        "profile": None,
        "version": None,
    }
    if result.accepted_profile is not None:
        payload["profile"] = _serialize(result.accepted_profile.profile.model_dump(mode="json"))
        payload["version"] = _serialize(result.accepted_profile.version.model_dump(mode="json"))
    return payload
