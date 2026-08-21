from contextlib import asynccontextmanager
import asyncio
import hmac
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.container import ApplicationContainer
from core.model_registry import validate_available_models, get_profile_readiness
from core.scheduler import scheduler_loop
from core.auth import AuthSettings, COOKIE_NAME, PUBLIC_PATHS, SAFE_METHODS, SessionManager, SessionValidationError, router as auth_router
from db.mongo import connect_db, close_db, database_ready
from routes.pipeline import router as pipeline_router
from routes.posts import router as posts_router
from routes.content_runs import router as content_runs_router
from routes.content_profiles import router as content_profiles_router
from routes.publishing import router as publishing_router
from routes.scheduling import router as scheduling_router


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_settings = AuthSettings.from_env()
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

os.makedirs("static/assets/renders", exist_ok=True)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

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


@app.middleware("http")
async def security_boundary(request: Request, call_next):
    path = request.url.path
    settings = getattr(request.app.state, "auth_settings", None)
    manager = getattr(request.app.state, "session_manager", None)
    is_public = path in PUBLIC_PATHS or path.startswith("/docs") or path == "/openapi.json"
    if settings is None or manager is None:
        if not is_public:
            return JSONResponse({"detail": "Authentication is not initialized"}, status_code=503)
    elif settings.enabled and not is_public:
        try:
            session = manager.verify(request.cookies.get(COOKIE_NAME))
        except SessionValidationError as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=401)
            response.delete_cookie(COOKIE_NAME, path="/")
            return response
        if request.method not in SAFE_METHODS:
            supplied_csrf = request.headers.get("X-CSRF-Token", "")
            if not supplied_csrf or not hmac.compare_digest(supplied_csrf, session["csrf"]):
                return JSONResponse({"detail": "Invalid CSRF token"}, status_code=403)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response

app.include_router(pipeline_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(content_runs_router, prefix="/api")
app.include_router(content_profiles_router, prefix="/api")
app.include_router(publishing_router, prefix="/api")
app.include_router(scheduling_router, prefix="/api")
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
