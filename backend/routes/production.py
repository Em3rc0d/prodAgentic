from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from core.execution_budget import production_deadline

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from agents.router import ModelRouter
from application.production.lifecycle import ContentProductionConflict, ContentProductionLifecycle
from application.production.r4_service import R4StructuredAgentCellService
from application.production.service import ProductionAuthorityError, ProductionContractViolation, ProductionDomainStop, RevisionBudgetExhausted, StructuredAgentCellService
from application.tenancy.context import require_tenant_context
from core.demo import build_demo_s3_service, demo_mode_enabled
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import RevisionStatus, GenerationRunState, ContentSpecV1, ResearchPackV1, canonical_sha256
from domain.production.evidence import load_run_evidence
from domain.production.failures import ProductionRecoveryAction, safe_exception_code
from domain.planning.models import ContentEditorialState
from application.production.recovery import ContentReplacementService, recovery_decision
from infrastructure.mongo.recovery import MongoRecoveryRepository, RecoveryConflict
from infrastructure.mongo.editorial_memory import MongoEditorialMemoryProjector
from domain.tenants.models import TenantContext
from infrastructure.evidence.google_grounding import GoogleGroundingEvidenceProvider
from infrastructure.agents.structured_text import RouterEditorAgent, RouterResearchAgent, RouterWriterAgent
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.profiles import MongoProfileRepository

router = APIRouter(tags=["mk1-production"])
logger = logging.getLogger(__name__)

R4_EVIDENCE_STAGE_SECONDS = 60.0
R4_EVIDENCE_ATTEMPT_SECONDS = 60.0


class ProduceTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_revision_id: str | None = Field(default=None, min_length=1, max_length=128)
    retry_of_run_id: str | None = Field(default=None, min_length=1, max_length=128)


class RecoverContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: ProductionRecoveryAction
    expected_run_id: str = Field(min_length=1, max_length=128)


def _serialize(model):
    return model.model_dump(mode="json") if hasattr(model, "model_dump") else model


def _safe_domain_stop_code(exc: Exception) -> str:
    message = str(exc)
    if "Research verdict NO_GO" in message:
        return "RESEARCH_NO_GO"
    if "Editor verdict REJECT" in message:
        return "EDITOR_REJECTED"
    if isinstance(exc, RevisionBudgetExhausted) or "revision budget" in message.lower():
        return "REVISION_BUDGET_EXHAUSTED"
    return "PRODUCTION_DOMAIN_STOP"


def _database(request: Request):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_ENABLED):
        raise HTTPException(status_code=404, detail="MK1 is not enabled")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return db


def _production_repository(request: Request, context: TenantContext) -> MongoProductionRepository:
    return MongoProductionRepository(_database(request), context)


def _repositories(request: Request, context: TenantContext):
    registry = getattr(request.app.state, "feature_flags", None)
    if registry is None or not registry.enabled(FeatureFlag.MK1_STRUCTURED_AGENT_CELL):
        raise HTTPException(status_code=404, detail="Structured agent cell is not enabled")
    db = _database(request)
    return MongoPlanningRepository(db, context), MongoProfileRepository(db, context), MongoProductionRepository(db, context)


def _isolated_router(router_instance: ModelRouter) -> ModelRouter:
    """Keep circuit-breaker state inside one independent production request.

    Provider adapters and routing policy are reusable configuration, but model/provider
    breaker state is runtime state. Sharing it across unrelated content items lets a
    transient failure in one GenerationRun suppress provider attempts in the next.
    """
    return router_instance.isolated()


def _evidence_router(router_instance: ModelRouter) -> ModelRouter:
    """Give grounded evidence a bounded budget separate from text-agent routing.

    Real R4.1 UAT showed Google Search grounding can legitimately exceed the
    generic 25-second attempt budget. Evidence gets one bounded 60-second route;
    Research/Writer/Editor retain the stricter defaults and the outer production
    deadline still caps the complete request at 150 seconds.
    """
    evidence_router = _isolated_router(router_instance)
    evidence_router.policy = replace(
        evidence_router.policy,
        max_stage_seconds=R4_EVIDENCE_STAGE_SECONDS,
        per_attempt_seconds=R4_EVIDENCE_ATTEMPT_SECONDS,
    )
    return evidence_router


def _build_service(request: Request, repository: MongoProductionRepository) -> StructuredAgentCellService:
    factory = getattr(request.app.state, "s3_service_factory", None)
    if factory is not None:
        service = factory(repository)
        if not isinstance(service, StructuredAgentCellService):
            raise RuntimeError("s3_service_factory must return StructuredAgentCellService")
        return service
    if demo_mode_enabled():
        return build_demo_s3_service(repository)
    container = getattr(request.app.state, "container", None)
    router_instance = getattr(container, "router", None) if container is not None else None
    if router_instance is None:
        raise HTTPException(status_code=503, detail="Model router is unavailable")
    agent_router = _isolated_router(router_instance)
    evidence_router = _evidence_router(router_instance)
    return R4StructuredAgentCellService(
        repository=repository,
        evidence_provider=GoogleGroundingEvidenceProvider(evidence_router),
        research_agent=RouterResearchAgent(agent_router),
        writer_agent=RouterWriterAgent(agent_router),
        editor_agent=RouterEditorAgent(agent_router),
    )


@router.get("/content-revisions")
async def list_content_revisions(
    request: Request,
    status: RevisionStatus | None = Query(default=RevisionStatus.REVIEWABLE),
    limit: int = Query(default=50, ge=1, le=100),
    context: TenantContext = Depends(require_tenant_context),
):
    production = _production_repository(request, context)
    revisions = (await production.list_revisions(context.tenant_id, status=status))[:limit]
    rows = []
    for revision in revisions:
        artifact = await production.get_artifact(context.tenant_id, revision.content_spec_ref)
        payload = (artifact or {}).get("payload", {}) if isinstance(artifact, dict) else {}
        rows.append({
            "revision_id": revision.revision_id,
            "content_id": revision.content_id,
            "run_id": revision.run_id,
            "status": revision.status.value,
            "created_at": revision.created_at.isoformat(),
            "title": payload.get("title"),
            "hook": payload.get("hook"),
            "format": payload.get("format"),
            "qa_report_id": revision.qa_report_id,
            "preview_asset_id": revision.asset_refs[0] if revision.asset_refs else None,
        })
    return {"revisions": rows, "count": len(rows)}


@router.get("/content-items/{content_id}")
async def get_content_item(content_id: str, request: Request, context: TenantContext = Depends(require_tenant_context)):
    planning, _, production = _repositories(request, context)
    item = await planning.get_content_item(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ContentItem not found")
    run = await production.latest_run(context.tenant_id, content_id)
    _, entries = await MongoRecoveryRepository(_database(request), context).read(item.batch_id)
    replacement = next((e for e in entries if e.rejected_content_id == content_id), None)
    decision = recovery_decision(item, run, replacement)
    if decision.action == ProductionRecoveryAction.RESUME_PIPELINE:
        try:
            revision = await production.get_revision(context.tenant_id, item.current_revision_id)
            if (revision is None or revision.run_id != run.run_id or revision.content_id != item.content_id
                    or revision.content_spec_ref != run.content_spec_ref or revision.status == RevisionStatus.SUPERSEDED):
                raise ValueError("Revision lineage mismatch")
            record = await production.get_artifact(context.tenant_id, revision.content_spec_ref)
            if record is None or record.get("artifact_type") != "ContentSpecV1":
                raise ValueError("Content authority unavailable")
            content = ContentSpecV1.model_validate(record["payload"])
            if (canonical_sha256(content) != revision.content_spec_digest
                    or record.get("digest") != revision.content_spec_digest or content.plan_id != run.plan_id):
                raise ValueError("Content digest mismatch")
            if run.evidence_bundle_ref or "EvidenceBundleV1@1" in run.contract_versions:
                research_record = await production.get_artifact(context.tenant_id, run.research_pack_ref)
                if research_record is None:
                    raise ValueError("Research unavailable")
                await load_run_evidence(production, context.tenant_id, run,
                                        ResearchPackV1.model_validate(research_record["payload"]))
        except (ValueError, KeyError, TypeError):
            decision = decision.model_copy(update={"action": ProductionRecoveryAction.HUMAN_ACTION_REQUIRED,
                "code": "RECOVERY_AUTHORITY_MISMATCH", "retryable": False,
                "safe_message": "The saved draft needs an integrity review before continuing."})
    return {"content_item": _serialize(item), "recovery": _serialize(decision)}


@router.post("/content-items/{content_id}/produce-text", status_code=201)
async def produce_text(content_id: str, body: ProduceTextRequest, request: Request, context: TenantContext = Depends(require_tenant_context)):
    planning, profiles, production = _repositories(request, context)
    item = await planning.get_content_item(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ContentItem not found")
    persisted_plan = await planning.get_plan_for_content(content_id)
    if persisted_plan is None:
        raise HTTPException(status_code=409, detail="ContentPlan evidence is unavailable")
    if persisted_plan.content_id != item.content_id or persisted_plan.batch_id != item.batch_id:
        raise HTTPException(status_code=409, detail="ContentPlan/ContentItem authority mismatch")
    profile = await profiles.get_version(item.profile_id, item.profile_version)
    if profile is None:
        raise HTTPException(status_code=409, detail="Frozen ProfileVersion is unavailable")
    service = _build_service(request, production)
    try:
        service.validate_authority(tenant_id=context.tenant_id, content_id=item.content_id, plan=persisted_plan.plan, plan_digest=persisted_plan.digest, profile=profile)
    except ProductionAuthorityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    previous = await production.latest_run(context.tenant_id, content_id)
    if body.retry_of_run_id is not None:
        if (previous is None or previous.run_id != body.retry_of_run_id
                or previous.state != GenerationRunState.FAILED or previous.failure is None
                or previous.failure.recovery_action != ProductionRecoveryAction.RETRY_PRODUCTION
                or item.editorial_state != ContentEditorialState.FAILED
                or previous.plan_digest != persisted_plan.digest or previous.profile_snapshot_digest != profile.digest):
            raise HTTPException(status_code=409, detail="Retry snapshot changed or is not eligible")
    if body.parent_revision_id is not None:
        parent = await production.get_revision(context.tenant_id, body.parent_revision_id)
        if parent is None or parent.content_id != content_id:
            raise HTTPException(status_code=409, detail="Parent revision does not belong to this content")
        parent_run = await production.get_run(context.tenant_id, parent.run_id)
        if (parent_run is None or parent_run.plan_digest != persisted_plan.digest
                or parent_run.profile_snapshot_digest != profile.digest):
            raise HTTPException(status_code=409, detail="Parent revision predecessor authority mismatch")
    lifecycle = ContentProductionLifecycle(planning)
    try:
        await lifecycle.begin(item.content_id, retry=body.retry_of_run_id is not None)
    except ContentProductionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    deadline_token = production_deadline.set(asyncio.get_running_loop().time() + 150.0)
    try:
        result = await service.produce_text(tenant_id=context.tenant_id, content_id=item.content_id, plan=persisted_plan.plan, plan_digest=persisted_plan.digest, profile=profile, parent_revision_id=body.parent_revision_id, retry_of_run_id=body.retry_of_run_id)
        await lifecycle.bind_text_revision(item.content_id, result.revision.revision_id)
    except ContentProductionConflict as exc:
        raise HTTPException(status_code=409, detail="Production authority changed; reload the item") from None
    except Exception as exc:
        # Read persisted authority, not exception bodies. Catch unclassified failures
        # while the run is still open and stop it with a safe non-retryable code.
        latest = await production.latest_run(context.tenant_id, content_id)
        if latest is not None and latest.state not in {GenerationRunState.FAILED, GenerationRunState.COMPLETED, GenerationRunState.CANCELLED}:
            latest = await service._fail_run(
                latest, safe_exception_code(exc, "PRODUCTION_INTERNAL_ERROR"),
                latest.state.value.lower(), retryable=False,
            )
        await lifecycle.fail(item.content_id)
        if latest is not None and latest.failure is not None:
            detail = {**latest.failure.model_dump(mode="json"), "content_id": content_id, "run_id": latest.run_id}
            status = 422 if latest.failure.recovery_action == ProductionRecoveryAction.REPLAN_CONTENT else 502
        else:
            detail = {"code": "PRODUCTION_INTERNAL_ERROR", "stage": "production", "retryable": False,
                      "recovery_action": "HUMAN_ACTION_REQUIRED", "content_id": content_id,
                      "safe_message": "Production stopped safely."}
            status = 502
        raise HTTPException(status_code=status, detail=detail) from None
    finally:
        production_deadline.reset(deadline_token)
    return {"run": _serialize(result.run), "revision": _serialize(result.revision), "research": _serialize(result.research), "content": _serialize(result.content), "editorial_review": _serialize(result.review), "creative_mode": "deterministic_demo" if demo_mode_enabled() else "model_router_r4", "next_stage": "S4_VISUAL_PLANNING" if result.content.format != "text" else "S6_QA"}


@router.get("/generation-runs/{run_id}")
async def get_generation_run(run_id: str, request: Request, context: TenantContext = Depends(require_tenant_context)):
    production = _production_repository(request, context)
    run = await production.get_run(context.tenant_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="GenerationRun not found")
    attempts = await production.list_agent_attempts(context.tenant_id, run_id)
    artifacts = {}
    for key, ref in (("evidence", run.evidence_bundle_ref), ("research", run.research_pack_ref), ("content", run.content_spec_ref), ("editorial_review", run.editorial_review_ref)):
        if ref:
            artifacts[key] = await production.get_artifact(context.tenant_id, ref)
    return {"run": _serialize(run), "attempts": [_serialize(item) for item in attempts], "artifacts": artifacts}


@router.get("/content-revisions/{revision_id}")
async def get_content_revision(revision_id: str, request: Request, context: TenantContext = Depends(require_tenant_context)):
    production = _production_repository(request, context)
    revision = await production.get_revision(context.tenant_id, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="ContentRevision not found")
    content = await production.get_artifact(context.tenant_id, revision.content_spec_ref)
    if content is None:
        raise HTTPException(status_code=409, detail="ContentSpec artifact is unavailable")
    return {"revision": _serialize(revision), "content": content}


@router.post("/content-items/{content_id}/recover")
async def recover_content(content_id: str, body: RecoverContentRequest, request: Request,
                          context: TenantContext = Depends(require_tenant_context)):
    planning, profiles, production = _repositories(request, context)
    if body.action == ProductionRecoveryAction.RETRY_PRODUCTION:
        return await produce_text(content_id, ProduceTextRequest(retry_of_run_id=body.expected_run_id), request, context)
    if body.action == ProductionRecoveryAction.RESUME_PIPELINE:
        snapshot = await get_content_item(content_id, request, context)
        decision = snapshot["recovery"]
        if decision["run_id"] != body.expected_run_id or decision["action"] != "RESUME_PIPELINE":
            raise HTTPException(status_code=409, detail="Saved draft authority changed; reload the item")
        revision_id = snapshot["content_item"]["current_revision_id"]
        revision_snapshot = await get_content_revision(revision_id, request, context)
        return {**revision_snapshot, "content_id": content_id, "next_action": "RESUME_PIPELINE"}
    if body.action == ProductionRecoveryAction.REPLAN_CONTENT:
        db = _database(request)
        recovery = MongoRecoveryRepository(db, context)
        service = ContentReplacementService(planning, production, profiles, recovery,
                                            MongoEditorialMemoryProjector(db, context, planning))
        try:
            entry = await service.replace(tenant_id=context.tenant_id, content_id=content_id,
                                          expected_run_id=body.expected_run_id)
        except RecoveryConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return {"replacement": entry.model_dump(mode="json"),
                "content_id": entry.replacement_item.content_id, "next_action": "PRODUCE"}
    raise HTTPException(status_code=409, detail="This recovery action requires inspection of the saved draft or operator attention")
