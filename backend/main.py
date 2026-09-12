from contextlib import asynccontextmanager
import asyncio
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.assets import prepare_asset_root
from core.container import ApplicationContainer
from core.demo import demo_mode_enabled
from core.model_registry import validate_available_models, get_profile_readiness
from core.scheduler import scheduler_loop
from core.auth import (
    AuthSettings,
    SessionManager,
    PUBLIC_PATHS,
    security_boundary,
    router as auth_router,
)
from core.cutover import cutover_readiness, production_cutover_boundary
from core.production import validate_production_environment
from core.feature_flags import FeatureFlag, FeatureFlagRegistry
from db.mongo import connect_db, close_db, database_ready, get_db
from routes.pipeline import router as pipeline_router
from routes.posts import router as posts_router
from routes.content_runs import router as content_runs_router
from routes.content_profiles import router as content_profiles_router
from routes.publishing import router as publishing_router
from routes.scheduling import router as scheduling_router
from routes.linkedin_oauth import router as linkedin_oauth_router
from routes.profiles import router as profiles_router
from routes.batches import router as batches_router
from routes.production import router as production_router
from routes.visual import router as visual_router
from routes.rendering import router as rendering_router
from routes.quality import router as quality_router
from routes.approval import router as approval_router
from routes.manual_export import router as manual_export_router
from routes.publishing_v2 import router as publishing_v2_router
from routes.analytics_v1 import router as analytics_v1_router


load_dotenv()
validate_production_environment()
PUBLIC_PATHS.add("/health/cutover")


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_settings = AuthSettings.from_env()
    app.state.auth_settings = auth_settings
    app.state.session_manager = SessionManager(auth_settings)
    app.state.feature_flags = FeatureFlagRegistry.from_env()
    await connect_db()
    container = ApplicationContainer()
    container.startup()
    app.state.container = container

    if container.client and not demo_mode_enabled():
        container.preflight_task = asyncio.create_task(validate_available_models(container.client))

    publish_authority = app.state.feature_flags.enabled(FeatureFlag.MK1_PUBLISH_WORKER)
    analytics_authority = app.state.feature_flags.enabled(FeatureFlag.MK1_ANALYTICS_WORKER)
    redis_transport = app.state.feature_flags.enabled(FeatureFlag.MK1_REDIS_TRANSPORT)
    if publish_authority:
        container.scheduler_task = None
        if redis_transport and get_db() is not None:
            from workers.publishing import s10_publish_loop

            container.s10_publish_task = asyncio.create_task(s10_publish_loop(get_db()))
        else:
            container.s10_publish_task = None
            print("[WARN] MK1_PUBLISH_WORKER enabled without Redis/Mongo readiness; MK0 scheduler remains disabled")
    else:
        container.scheduler_task = asyncio.create_task(scheduler_loop())
        container.s10_publish_task = None

    if analytics_authority and redis_transport and get_db() is not None:
        from workers.analytics import s11_analytics_loop

        container.s11_analytics_task = asyncio.create_task(s11_analytics_loop(get_db()))
    else:
        container.s11_analytics_task = None
        if analytics_authority:
            print("[WARN] MK1_ANALYTICS_WORKER enabled without Redis/Mongo readiness; analytics collection is delayed")

    yield

    for task_name in ("preflight_task", "scheduler_task", "s10_publish_task", "s11_analytics_task"):
        task = getattr(container, task_name, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    await container.shutdown()
    await close_db()


app = FastAPI(
    title="AI Multi-Agent Content Engine",
    description="Agentic LinkedIn content pipeline with durable review, approval, scheduling, publication and analytics contracts",
    version="1.0.0",
    lifespan=lifespan,
)

asset_root = prepare_asset_root()
app.mount("/assets", StaticFiles(directory=str(asset_root)), name="assets")

allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(production_cutover_boundary)
app.middleware("http")(security_boundary)

app.include_router(pipeline_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(content_runs_router, prefix="/api")
app.include_router(content_profiles_router, prefix="/api")
app.include_router(publishing_router, prefix="/api")
app.include_router(scheduling_router, prefix="/api")
app.include_router(linkedin_oauth_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")
app.include_router(batches_router, prefix="/api")
app.include_router(production_router, prefix="/api")
app.include_router(visual_router, prefix="/api")
app.include_router(rendering_router, prefix="/api")
app.include_router(quality_router, prefix="/api")
app.include_router(approval_router, prefix="/api")
app.include_router(manual_export_router, prefix="/api")
app.include_router(publishing_v2_router, prefix="/api")
app.include_router(analytics_v1_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AI Multi-Agent Content Engine", "description": "API is running. See /health/ready for status.", "docs": "/docs"}


@app.get("/health/live")
def health_live():
    return {"status": "alive"}


@app.get("/health/cutover")
def health_cutover(request: Request):
    payload, status_code = cutover_readiness(request)
    return JSONResponse(content=payload, status_code=status_code)


@app.get("/health/ready")
def health_ready(request: Request):
    container = getattr(request.app.state, "container", None)
    if not container:
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": "Application container unavailable"}), media_type="application/json", status_code=503)

    if getattr(container, "config_error", None):
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": container.config_error}), media_type="application/json", status_code=503)

    if not database_ready():
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": "Database unavailable"}), media_type="application/json", status_code=503)

    if demo_mode_enabled():
        return {
            "status": "READY_DEMO",
            "message": "Deterministic local demo agents enabled; Mongo, rendering, QA, review and approval remain real.",
        }

    if not container.client:
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": "Missing API Key"}), media_type="application/json", status_code=503)

    status = get_profile_readiness()
    if status in ("READY", "READY_WITH_STALE_CACHE"):
        return {"status": status}
    if status in ("DEGRADED", "DEGRADED_WITH_STALE_CACHE"):
        return {"status": status, "message": "Some fallbacks or primary models are missing."}

    from fastapi import Response
    return Response(content=json.dumps({"status": status}), media_type="application/json", status_code=503)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
