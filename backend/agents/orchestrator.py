import json
import asyncio
import uuid
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
    """Run idea generation via the async IdeaGeneratorAgent."""
    return await _idea_agent.generate_ideas(topic, style)

async def run_pipeline_stream(
    idea: str, topic: str, style: str
) -> AsyncGenerator[dict, None]:
    run_id = str(uuid.uuid4())
    
    research_ref = [""]
    draft_ref = [""]
    final_ref = [""]

    async def run_stage(agent_stream_func, stage_name, profile, output_ref):
        from agents.router import StageFailedException
        attempt_id = str(uuid.uuid4())
        attempt_number = 1
        
        while True:
            try:
                async for event_type, payload in agent_stream_func(attempt_id):
                    if event_type == "model_selected":
                        yield _sse(
                            "stage_attempt_started", 
                            stage_name=stage_name, 
                            model_profile=profile, 
                            selected_model=payload,
                            attempt_id=attempt_id,
                            attempt_number=attempt_number,
                            run_id=run_id
                        )
                    elif event_type == "chunk":
                        output_ref[0] += payload
                        yield _sse("chunk", stage_name=stage_name, text=payload, attempt_id=attempt_id, run_id=run_id)
                
                # Success
                yield _sse("stage_done", stage_name=stage_name, content=output_ref[0], run_id=run_id)
                break
                
            except StageFailedException as e:
                yield _sse("stage_attempt_reset", stage_name=stage_name, reason=str(e), attempt_id=attempt_id, run_id=run_id)
                output_ref[0] = ""
                attempt_number += 1
                attempt_id = str(uuid.uuid4())
                if attempt_number > 3:
                    raise Exception(f"Max stage reset attempts exceeded for {stage_name}") from e
    try:
        # ── Stage 1: Research ──────────────────────────────────────────────────
        def research_stream(attempt_id): return _research_agent.stream(idea, attempt_id)
        async for event in run_stage(research_stream, "research", _research_agent.profile.value, research_ref): yield event
            
        # ── Stage 2: Write ─────────────────────────────────────────────────────
        def writer_stream(attempt_id): return _writer_agent.stream(idea, research_ref[0], style, attempt_id)
        async for event in run_stage(writer_stream, "write", _writer_agent.profile.value, draft_ref): yield event

        # ── Stage 3: Edit ──────────────────────────────────────────────────────
        def edit_stream(attempt_id): return _editor_agent.stream(draft_ref[0], attempt_id)
        async for event in run_stage(edit_stream, "edit", _editor_agent.profile.value, final_ref): yield event
        
    except Exception as e:
        yield _sse("stage_failed", stage_name="unknown", reason=str(e), run_id=run_id)
        return

    # ── Persist to MongoDB ─────────────────────────────────────────────────
    post_id = None
    try:
        db = get_db()
        if db is not None:
            doc = {
                "topic": topic,
                "style": style,
                "idea": idea,
                "research_output": research_ref[0],
                "draft_content": draft_ref[0],
                "final_content": final_ref[0],
                "status": "DRAFT",
                "created_at": datetime.now(timezone.utc),
                "performance": {"likes": 0, "impressions": 0, "comments": 0},
            }
            result = await db["posts"].insert_one(doc)
            post_id = str(result.inserted_id)
    except Exception as e:
        print(f"[WARN] MongoDB save error: {e}")

    yield _sse("complete", post_id=post_id, final_post=final_ref[0])
