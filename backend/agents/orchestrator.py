import json
import asyncio
import uuid
from typing import AsyncGenerator
from datetime import datetime, timezone

from .idea_generator import IdeaGeneratorAgent
from .research_agent import ResearchAgent
from .content_writer import ContentWriterAgent
from .editor_agent import EditorAgent
from .visual_agent import VisualAgent
from db.mongo import get_db
from agents.router import AttemptStarted, ContentChunk, AttemptFailed, AttemptResetRequired, AttemptCompleted, RoutingExhausted, ValidationWarning
from core.context import GenerationContext, LanguageCode, TargetLanguageCode, ImagePromptLanguageCode
from core.language import language_detector

def _sse(stage: str, **kwargs) -> dict:
    """Build a Server-Sent Events payload dict."""
    return {"data": json.dumps({"stage": stage, **kwargs})}

class PipelineAbortError(Exception):
    pass

class PipelineOrchestrator:
    def __init__(self, router):
        self.router = router
        self.idea_agent = IdeaGeneratorAgent(router)
        self.research_agent = ResearchAgent(router)
        self.writer_agent = ContentWriterAgent(router)
        self.editor_agent = EditorAgent(router)
        self.visual_agent = VisualAgent(router)

    def _resolve_context(self, topic: str, style: str, target_language: str, image_prompt_language: str) -> GenerationContext:
        import os
        target_lang = TargetLanguageCode(target_language)

        # Always detect source language
        detect_result = language_detector.detect(topic)
        detected_lang = detect_result.language
        confidence = detect_result.confidence

        # Single authoritative config: ApplicationSettings.load() already validated this at startup
        # Read here as a pass-through; ValueError propagates naturally if not set
        default_lang_str = os.environ.get("APP_DEFAULT_LANGUAGE", "")
        if not default_lang_str:
            raise ValueError(
                "APP_DEFAULT_LANGUAGE is required. Set it to one of: es, en, pt"
            )
        default_lang = LanguageCode(default_lang_str)

        if target_lang == TargetLanguageCode.AUTO:
            resolved_lang = detected_lang if detected_lang != LanguageCode.UNKNOWN else default_lang
        else:
            resolved_lang = LanguageCode(target_lang.value)

        img_lang = ImagePromptLanguageCode(image_prompt_language)

        return GenerationContext(
            run_id=str(uuid.uuid4()),
            topic=topic,
            style=style,
            requested_source_language=LanguageCode.AUTO,
            detected_source_language=detected_lang,
            source_detection_confidence=confidence,
            requested_target_language=LanguageCode(target_lang.value),
            resolved_target_language=resolved_lang,
            image_prompt_language=img_lang.to_language_code()
        )

    async def generate_ideas(self, topic: str, style: str, target_language: str = "es") -> list[str]:
        context = self._resolve_context(topic, style, target_language, "en")
        return await self.idea_agent.generate_ideas(context)

    async def run_pipeline_stream(self, idea: str, topic: str, style: str, target_language: str = "es", image_prompt_language: str = "en") -> AsyncGenerator[dict, None]:
        context = self._resolve_context(topic, style, target_language, image_prompt_language)
        
        research_ref = [""]
        draft_ref = [""]
        final_ref = [""]
        visual_ref = [""]

        async def run_stage(agent_stream_func, stage_name, profile, output_ref, ignore_failure=False, stage_flags=None):
            if stage_flags is None:
                stage_flags = {}
                
            attempt_number = 0
            event_sequence = 0
            
            try:
                async for event in agent_stream_func(context):
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
                            run_id=context.run_id,
                            event_sequence=event_sequence
                        )
                    elif isinstance(event, ContentChunk):
                        output_ref[0] += event.text
                        yield _sse(
                            "stage.chunk",
                            stage_name=stage_name,
                            text=event.text,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence
                        )
                    elif isinstance(event, AttemptResetRequired):
                        yield _sse(
                            "stage.attempt_reset",
                            stage_name=stage_name,
                            reason=event.reason,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence
                        )
                        output_ref[0] = ""
                    elif isinstance(event, AttemptFailed):
                        yield _sse(
                            "stage.attempt_failed",
                            stage_name=stage_name,
                            reason=event.reason,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence
                        )
                    elif isinstance(event, ValidationWarning):
                        stage_flags["has_validation_warning"] = True
                        yield _sse(
                            "stage.validation_warning",
                            code=event.code,
                            stage_name=stage_name,
                            expected_language=event.expected_language,
                            detected_language=event.detected_language,
                            confidence=event.confidence,
                            reason=event.reason,
                            run_id=context.run_id,
                            event_sequence=event_sequence
                        )
                    elif isinstance(event, AttemptCompleted):
                        pass
                    elif isinstance(event, RoutingExhausted):
                        raise Exception(event.reason)
                
                event_sequence += 1
                yield _sse("stage.completed", stage_name=stage_name, content=output_ref[0], run_id=context.run_id, event_sequence=event_sequence)
            except Exception as e:
                event_sequence += 1
                stage_flags["failed"] = True
                if ignore_failure:
                    yield _sse(f"{stage_name}.failed", reason=str(e), retryable=True)
                else:
                    yield _sse("stage.failed", stage_name=stage_name, reason=str(e), run_id=context.run_id, event_sequence=event_sequence)
                    raise PipelineAbortError()

        try:
            def research_stream(ctx): return self.research_agent.stream(idea, context=ctx, attempt_id=None)
            async for event in run_stage(research_stream, "research", self.research_agent.profile.value, research_ref): yield event
                
            def writer_stream(ctx): return self.writer_agent.stream(idea, research_ref[0], context=ctx, attempt_id=None)
            async for event in run_stage(writer_stream, "write", self.writer_agent.profile.value, draft_ref): yield event

            final_flags = {}
            def edit_stream(ctx): return self.editor_agent.stream(draft_ref[0], context=ctx, attempt_id=None)
            async for event in run_stage(edit_stream, "edit", self.editor_agent.profile.value, final_ref, stage_flags=final_flags): yield event
            
            final_status = "NEEDS_LANGUAGE_REVIEW" if final_flags.get("has_validation_warning") else "READY"
        except PipelineAbortError:
            return
        except Exception as e:
            yield _sse("stage.failed", stage_name="unknown", reason=str(e), run_id=context.run_id)
            return

        yield _sse("pipeline.text_completed", final_status=final_status, final_post=final_ref[0], run_id=context.run_id)

        visual_status = "FAILED"
        try:
            yield _sse("visual.prompt_started", run_id=context.run_id)
            
            def visual_stream(ctx): return self.visual_agent.stream(final_ref[0], context=ctx, attempt_id=None)
            
            visual_flags = {}
            async for event in run_stage(visual_stream, "visual", self.visual_agent.profile.value, visual_ref, ignore_failure=True, stage_flags=visual_flags):
                yield event
                
            # Only set READY if we actually received stage.completed without failing
            if visual_ref[0] and not visual_flags.get("failed"):
                visual_status = "READY"
                yield _sse("visual.prompt_completed", content=visual_ref[0], run_id=context.run_id)
            else:
                yield _sse("visual.prompt_failed", reason="Partial failure or empty output", run_id=context.run_id)
                
        except Exception as e:
            yield _sse("visual.prompt_failed", reason=str(e), run_id=context.run_id)

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
                    "visual_prompt": visual_ref[0] if visual_status == "READY" else None,
                    "status": "DRAFT",
                    "created_at": datetime.now(timezone.utc),
                    "performance": {"likes": 0, "impressions": 0, "comments": 0},
                }
                result = await db["posts"].insert_one(doc)
                post_id = str(result.inserted_id)
        except Exception as e:
            print(f"[WARN] MongoDB save error: {e}")

        yield _sse("complete", final_status=final_status, visual_status=visual_status, post_id=post_id, final_post=final_ref[0], visual_prompt=visual_ref[0] if visual_status == "READY" else None)
