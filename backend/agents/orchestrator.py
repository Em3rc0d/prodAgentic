import json
import asyncio
from typing import AsyncGenerator
from datetime import datetime, timezone

from .idea_generator import IdeaGeneratorAgent
from .research_agent import ResearchAgent
from .content_writer import ContentWriterAgent
from .editor_agent import EditorAgent
from db.mongo import get_db

# Singleton agents — initialized once at startup
_idea_agent = IdeaGeneratorAgent()
_research_agent = ResearchAgent()
_writer_agent = ContentWriterAgent()
_editor_agent = EditorAgent()


def _sse(stage: str, **kwargs) -> dict:
    """Build a Server-Sent Events payload dict."""
    return {"data": json.dumps({"stage": stage, **kwargs})}


async def generate_ideas(topic: str, style: str) -> list[str]:
    """Run idea generation in a thread (sync Gemini call)."""
    return await asyncio.to_thread(_idea_agent.generate_ideas, topic, style)


async def run_pipeline_stream(
    idea: str, topic: str, style: str
) -> AsyncGenerator[dict, None]:
    """
    Streams the full research → write → edit pipeline as SSE events.
    Each yielded dict has a "data" key with JSON string payload.
    """
    research_text = ""
    draft_text = ""
    final_text = ""

    # ── Stage 1: Research ──────────────────────────────────────────────────
    yield _sse("stage_start", stage_name="research")
    async for chunk in _research_agent.stream(idea):
        research_text += chunk
        yield _sse("chunk", stage_name="research", text=chunk)
    yield _sse("stage_done", stage_name="research", content=research_text)

    # ── Stage 2: Write ─────────────────────────────────────────────────────
    yield _sse("stage_start", stage_name="write")
    async for chunk in _writer_agent.stream(idea, research_text, style):
        draft_text += chunk
        yield _sse("chunk", stage_name="write", text=chunk)
    yield _sse("stage_done", stage_name="write", content=draft_text)

    # ── Stage 3: Edit ──────────────────────────────────────────────────────
    yield _sse("stage_start", stage_name="edit")
    async for chunk in _editor_agent.stream(draft_text):
        final_text += chunk
        yield _sse("chunk", stage_name="edit", text=chunk)
    yield _sse("stage_done", stage_name="edit", content=final_text)

    # ── Persist to MongoDB ─────────────────────────────────────────────────
    post_id = None
    try:
        db = get_db()
        if db is not None:
            doc = {
                "topic": topic,
                "style": style,
                "idea": idea,
                "research_output": research_text,
                "draft_content": draft_text,
                "final_content": final_text,
                "status": "DRAFT",
                "created_at": datetime.now(timezone.utc),
                "performance": {"likes": 0, "impressions": 0, "comments": 0},
            }
            result = await db["posts"].insert_one(doc)
            post_id = str(result.inserted_id)
    except Exception as e:
        print(f"[WARN] MongoDB save error: {e}")

    yield _sse("complete", post_id=post_id, final_post=final_text)
