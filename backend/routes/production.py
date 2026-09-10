from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from application.production.lifecycle import ContentProductionConflict, ContentProductionLifecycle
from application.production.service import ProductionAuthorityError, ProductionContractViolation, ProductionDomainStop, RevisionBudgetExhausted, StructuredAgentCellService
from application.tenancy.context import require_tenant_context
from core.demo import build_demo_s3_service, demo_mode_enabled
from core.feature_flags import FeatureFlag
from db.mongo import get_db
from domain.production.models import RevisionStatus
from domain.tenants.models import TenantContext
from infrastructure.agents.structured_text import RouterEditorAgent, RouterResearchAgent, RouterWriterAgent
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.profiles import MongoProfileRepository

router = APIRouter(tags=["mk1-production"])

class ProduceTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_revision_id: str | None = Field(default=None, min_length=1, max_length=128)

def _serialize(model):
    return model.model_dump(mode="json") if hasattr(model, "model_dump") else model

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
    return StructuredAgentCellService(repository=repository, research_agent=RouterResearchAgent(router_instance), writer_agent=RouterWriterAgent(router_instance), editor_agent=RouterEditorAgent(router_instance))

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
        })
    return {"revisions": rows, "count": len(rows)}

@router.post("/content-items/{content_id}/produce-text", status_code=201)
async def produce_text(content_id: str, body: ProduceTextRequest, request: Request, context: TenantContext = Depends(require_tenant_context)):
    planning, profiles, production = _repositories(request, context)
    item = await planning.get_content_item(content_id)
    if item is None: raise HTTPException(status_code=404, detail="ContentItem not found")
    persisted_plan = await planning.get_plan_for_content(content_id)
    if persisted_plan is None: raise HTTPException(status_code=409, detail="ContentPlan evidence is unavailable")
    if persisted_plan.content_id != item.content_id or persisted_plan.batch_id != item.batch_id: raise HTTPException(status_code=409, detail="ContentPlan/ContentItem authority mismatch")
    profile = await profiles.get_version(item.profile_id, item.profile_version)
    if profile is None: raise HTTPException(status_code=409, detail="Frozen ProfileVersion is unavailable")
    service = _build_service(request, production)
    lifecycle = ContentProductionLifecycle(planning)
    try: await lifecycle.begin(item.content_id)
    except ContentProductionConflict as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        result = await service.produce_text(tenant_id=context.tenant_id, content_id=item.content_id, plan=persisted_plan.plan, plan_digest=persisted_plan.digest, profile=profile, parent_revision_id=body.parent_revision_id)
        await lifecycle.bind_text_revision(item.content_id, result.revision.revision_id)
    except ProductionAuthorityError as exc:
        await lifecycle.fail(item.content_id); raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProductionDomainStop as exc:
        await lifecycle.fail(item.content_id); raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RevisionBudgetExhausted as exc:
        await lifecycle.fail(item.content_id); raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProductionContractViolation as exc:
        await lifecycle.fail(item.content_id); raise HTTPException(status_code=502, detail="Structured production failed before a valid text revision was produced") from exc
    except ContentProductionConflict as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        await lifecycle.fail(item.content_id); raise
    return {"run": _serialize(result.run), "revision": _serialize(result.revision), "research": _serialize(result.research), "content": _serialize(result.content), "editorial_review": _serialize(result.review), "next_stage": "S4_VISUAL_PLANNING" if result.content.format != "text" else "S6_QA"}

@router.get("/generation-runs/{run_id}")
async def get_generation_run(run_id: str, request: Request, context: TenantContext = Depends(require_tenant_context)):
    production = _production_repository(request, context)
    run = await production.get_run(context.tenant_id, run_id)
    if run is None: raise HTTPException(status_code=404, detail="GenerationRun not found")
    attempts = await production.list_agent_attempts(context.tenant_id, run_id)
    artifacts = {}
    for key, ref in (("research", run.research_pack_ref), ("content", run.content_spec_ref), ("editorial_review", run.editorial_review_ref)):
        if ref: artifacts[key] = await production.get_artifact(context.tenant_id, ref)
    return {"run": _serialize(run), "attempts": [_serialize(item) for item in attempts], "artifacts": artifacts}

@router.get("/content-revisions/{revision_id}")
async def get_content_revision(revision_id: str, request: Request, context: TenantContext = Depends(require_tenant_context)):
    production = _production_repository(request, context)
    revision = await production.get_revision(context.tenant_id, revision_id)
    if revision is None: raise HTTPException(status_code=404, detail="ContentRevision not found")
    content = await production.get_artifact(context.tenant_id, revision.content_spec_ref)
    if content is None: raise HTTPException(status_code=409, detail="ContentSpec artifact is unavailable")
    return {"revision": _serialize(revision), "content": content}
