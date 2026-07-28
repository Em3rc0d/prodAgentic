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
from agents.router import AttemptStarted, ContentChunk, AttemptFailed, AttemptResetRequired, AttemptCompleted, RoutingExhausted

def _sse(stage: str, **kwargs) -> dict:
    """Build a Server-Sent Events payload dict."""
    return {"data": json.dumps({"stage": stage, **kwargs})}

class PipelineOrchestrator:
    def __init__(self, router):
        self.router = router
        self.idea_agent = IdeaGeneratorAgent(router)
        self.research_agent = ResearchAgent(router)
        self.writer_agent = ContentWriterAgent(router)
        self.editor_agent = EditorAgent(router)

    async def generate_ideas(self, topic: str, style: str) -> list[str]:
        return await self.idea_agent.generate_ideas(topic, style)

    async def run_pipeline_stream(self, idea: str, topic: str, style: str) -> AsyncGenerator[dict, None]:
        run_id = str(uuid.uuid4())
        
        research_ref = [""]
        draft_ref = [""]
        final_ref = [""]

        async def run_stage(agent_stream_func, stage_name, profile, output_ref):
            attempt_number = 0
            event_sequence = 0
            
            async for event in agent_stream_func(run_id=run_id):
                event_sequence += 1
                if isinstance(event, AttemptStarted):
                    attempt_number += 1
                    yield _sse(
                        "stage.attempt_started",
                        stage_name=stage_name,
                        model_profile=profile,
                        selected_model=event.model_id,
                        provider=event.provider,
                        attempt_id=event.attempt_id,
                        attempt_number=attempt_number,
                        run_id=run_id,
                        event_sequence=event_sequence
                    )
                elif isinstance(event, ContentChunk):
                    output_ref[0] += event.text
                    yield _sse(
                        "stage.chunk",
                        stage_name=stage_name,
                        text=event.text,
                        attempt_id=event.attempt_id,
                        run_id=run_id,
                        event_sequence=event_sequence
                    )
                elif isinstance(event, AttemptResetRequired):
                    yield _sse(
                        "stage.attempt_reset",
                        stage_name=stage_name,
                        reason=event.reason,
                        attempt_id=event.attempt_id,
                        run_id=run_id,
                        event_sequence=event_sequence
                    )
                    output_ref[0] = ""
                elif isinstance(event, AttemptFailed):
                    yield _sse(
                        "stage.attempt_failed",
                        stage_name=stage_name,
                        reason=event.reason,
                        attempt_id=event.attempt_id,
                        run_id=run_id,
                        event_sequence=event_sequence
                    )
                elif isinstance(event, AttemptCompleted):
                    pass
                elif isinstance(event, RoutingExhausted):
                    raise Exception(event.reason)
            
            event_sequence += 1
            yield _sse("stage.completed", stage_name=stage_name, content=output_ref[0], run_id=run_id, event_sequence=event_sequence)

        try:
            # Stage 1: Research
            def research_stream(run_id): return self.research_agent.stream(idea, attempt_id=None, run_id=run_id)
            async for event in run_stage(research_stream, "research", self.research_agent.profile.value, research_ref): yield event
                
            # Stage 2: Write
            def writer_stream(run_id): return self.writer_agent.stream(idea, research_ref[0], style, attempt_id=None, run_id=run_id)
            async for event in run_stage(writer_stream, "write", self.writer_agent.profile.value, draft_ref): yield event

            # Stage 3: Edit
            def edit_stream(run_id): return self.editor_agent.stream(draft_ref[0], attempt_id=None, run_id=run_id)
            async for event in run_stage(edit_stream, "edit", self.editor_agent.profile.value, final_ref): yield event
            
        except Exception as e:
            yield _sse("stage.failed", stage_name="unknown", reason=str(e), run_id=run_id)
            return

        # Persist to MongoDB
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

