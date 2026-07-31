from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from db.mongo import connect_db, close_db
from routes.pipeline import router as pipeline_router
from routes.posts import router as posts_router
from dotenv import load_dotenv
import asyncio
from core.model_registry import validate_available_models, get_profile_readiness
from core.container import ApplicationContainer
import json

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to MongoDB. Shutdown: close connection."""
    await connect_db()
    
    container = ApplicationContainer()
    container.startup()
    app.state.container = container
    
    if container.client:
        container.preflight_task = asyncio.create_task(validate_available_models(container.client))
        
    yield
    
    if getattr(container, 'preflight_task', None) and not container.preflight_task.done():
        container.preflight_task.cancel()
        try:
            await container.preflight_task
        except asyncio.CancelledError:
            pass
            
    await container.shutdown()
    await close_db()


app = FastAPI(
    title="AI Multi-Agent Content Engine",
    description="5-agent LinkedIn content pipeline with formal Model Registry & Attempt-aware Streaming",
    version="1.0.0",
    lifespan=lifespan,
)

import os
from fastapi.staticfiles import StaticFiles

# Ensure static/assets/renders exists before mounting
os.makedirs("static/assets/renders", exist_ok=True)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api")
app.include_router(posts_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "🚀 AI Multi-Agent Content Engine",
        "description": "API is running. See /health/ready for status.",
        "docs": "/docs",
    }


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
        
    status = get_profile_readiness()
    if status in ("READY", "READY_WITH_STALE_CACHE"):
        return {"status": status}
    elif status in ("DEGRADED", "DEGRADED_WITH_STALE_CACHE"):
        return {"status": status, "message": "Some fallbacks or primary models are missing."}
    else:
        from fastapi import Response
        return Response(content=json.dumps({"status": status}), media_type="application/json", status_code=503)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
