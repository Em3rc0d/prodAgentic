from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.mongo import connect_db, close_db
from routes.pipeline import router as pipeline_router
from routes.posts import router as posts_router
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to MongoDB. Shutdown: close connection."""
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="AI Multi-Agent Content Engine",
    description="5-agent LinkedIn content pipeline powered by Gemini 2.0 Flash",
    version="1.0.0",
    lifespan=lifespan,
)

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
        "model": "gemini-2.0-flash",
        "agents": ["idea-generator", "research", "content-writer", "editor"],
        "docs": "/docs",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
