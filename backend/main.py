from contextlib import asynccontextmanager
import asyncio
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.assets import prepare_asset_root
from core.container import ApplicationContainer
from core.model_registry import validate_available_models, get_profile_readiness
from core.scheduler import scheduler_loop
from core.auth import AuthSettings, SessionManager, security_boundary, router as auth_router
from core.deployment import validate_cross_origin_auth
from db.mongo import connect_db, close_db, database_ready
from routes.pipeline import router as pipeline_router
from routes.posts import router as posts_router
from routes.content_runs import router as content_runs_router
from routes.content_profiles import router as content_profiles_router
from routes.publishing import router as publishing_router
from routes.scheduling import router as scheduling_router
from routes.linkedin_oauth import router as linkedin_oauth_router


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_settings = AuthSettings.from_env()
    validate_cross_origin_auth(auth_settings)
    app.state.auth_settings = auth_settings
    app.state.session_manager = SessionManager(auth_settings)
    await connect_db()
    container = ApplicationContainer()
    container.startup()
    app.state.container = container

    if container.client:
        container.preflight_task = asyncio.create_task(validate_available_models(container.client))
    container.scheduler_task = asyncio.create_task(scheduler_loop())

    yield

    for task_name in ("preflight_task", "scheduler_task"):
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
    description="Agentic LinkedIn content pipeline with durable review, approval, scheduling and publication contracts",
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


app.middleware("http")(security_boundary)

app.include_router(pipeline_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(content_runs_router, prefix="/api")
app.include_router(content_profiles_router, prefix="/api")
app.include_router(publishing_router, prefix="/api")
app.include_router(scheduling_router, prefix="/api")
app.include_router(linkedin_oauth_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AI Multi-Agent Content Engine", "description": "API is running. See /health/ready for status.", "docs": "/docs"}


@app.get("/health/live")
def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready(request: Request):
    container = getattr(request.app.state, "container", None)
    if not container or not container.client:
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": "Missing API Key"}), media_type="application/json", status_code=503)

    if getattr(container, "config_error", None):
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": container.config_error}), media_type="application/json", status_code=503)

    if not database_ready():
        from fastapi import Response
        return Response(content=json.dumps({"status": "NOT_READY", "message": "Database unavailable"}), media_type="application/json", status_code=503)

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
