import json
import logging
import uuid
from typing import AsyncGenerator
from datetime import datetime, timezone

from .idea_generator import IdeaGeneratorAgent
from .research_agent import ResearchAgent
from .content_writer import ContentWriterAgent
from .editor_agent import EditorAgent
from .visual_agent import VisualAgent
from db.mongo import get_db
from db.content_runs import ContentRunRepository
from agents.router import AttemptStarted, ContentChunk, AttemptFailed, AttemptResetRequired, AttemptCompleted, RoutingExhausted, ValidationWarning
from core.context import GenerationContext, LanguageCode, TargetLanguageCode, ImagePromptLanguageCode
from core.language import language_detector
from core.content_memory import ContentMemoryService
from core.grounding import FactualEnvelopeBuilder
from models.grounding import SourcePacket


logger = logging.getLogger(__name__)


def _sse(stage: str, **kwargs) -> dict:
    return {"data": json.dumps({"stage": stage, **kwargs})}


class PipelineAbortError(Exception):
    pass


class PipelineOrchestrator:
    def __init__(self, router, workspace_id: str = "legacy-default"):
        self.router = router
        self.workspace_id = workspace_id
        self.idea_agent = IdeaGeneratorAgent(router)
        self.research_agent = ResearchAgent(router)
        self.writer_agent = ContentWriterAgent(router)
        self.editor_agent = EditorAgent(router)
        self.visual_agent = VisualAgent(router)
        self.content_runs = ContentRunRepository()
        self.content_memory = ContentMemoryService()

    async def _persist(self, method, *args, **kwargs):
        """Best-effort persistence for non-terminal stage detail and projections."""
        try:
            return await method(*args, **kwargs)
        except Exception as exc:
            logger.warning("ContentRun auxiliary persistence degraded: %s", exc)
            return None

    async def _persist_required(self, method, *args, **kwargs):
        """Persist an authoritative lifecycle boundary or fail the pipeline closed."""
        try:
            return await method(*args, **kwargs)
        except Exception as exc:
            logger.error("Authoritative ContentRun persistence failed: %s", exc)
            raise PipelineAbortError("Authoritative ContentRun persistence failed") from exc

    def _resolve_context(
        self,
        topic: str,
        style: str,
        target_language: str,
        image_prompt_language: str,
        content_profile_id: str | None = None,
        content_profile_snapshot: dict | None = None,
    ) -> GenerationContext:
        import os
        target_lang = TargetLanguageCode(target_language)
        detect_result = language_detector.detect(topic)
        detected_lang = detect_result.language
        confidence = detect_result.confidence

        default_lang_str = os.environ.get("APP_DEFAULT_LANGUAGE", "")
        if not default_lang_str:
            raise ValueError("APP_DEFAULT_LANGUAGE is required. Set it to one of: es, en, pt")
        default_lang = LanguageCode(default_lang_str)

        if target_lang == TargetLanguageCode.AUTO:
            resolved_lang = detected_lang if detected_lang != LanguageCode.UNKNOWN else default_lang
        else:
            resolved_lang = LanguageCode(target_lang.value)

        img_lang = ImagePromptLanguageCode(image_prompt_language)
        audience = None
        if content_profile_snapshot and content_profile_snapshot.get("audience"):
            audience = ", ".join(content_profile_snapshot["audience"])

        return GenerationContext(
            run_id=str(uuid.uuid4()),
            workspace_id=self.workspace_id,
            topic=topic,
            style=style,
            requested_source_language=LanguageCode.AUTO,
            detected_source_language=detected_lang,
            source_detection_confidence=confidence,
            requested_target_language=LanguageCode(target_lang.value),
            resolved_target_language=resolved_lang,
            image_prompt_language=img_lang.to_language_code(),
            audience=audience,
            content_profile_id=content_profile_id,
            content_profile_snapshot=content_profile_snapshot,
        )

    async def generate_ideas(
        self,
        topic: str,
        style: str,
        target_language: str = "es",
        content_profile_id: str | None = None,
        content_profile_snapshot: dict | None = None,
    ) -> list[str]:
        context = self._resolve_context(
            topic,
            style,
            target_language,
            "en",
            content_profile_id,
            content_profile_snapshot,
        )
        return await self.idea_agent.generate_ideas(context)

    async def run_pipeline_stream(
        self,
        idea: str,
        topic: str,
        style: str,
        target_language: str = "es",
        image_prompt_language: str = "en",
        content_profile_id: str | None = None,
        content_profile_snapshot: dict | None = None,
        source_packet: SourcePacket | None = None,
    ) -> AsyncGenerator[dict, None]:
        context = self._resolve_context(
            topic,
            style,
            target_language,
            image_prompt_language,
            content_profile_id,
            content_profile_snapshot,
        )

        factual_envelope = None
        factual_envelope_text = None
        if source_packet is not None:
            if source_packet.workspace_id != context.workspace_id:
                yield _sse(
                    "error",
                    reason="Source packet workspace does not match authoritative ContentRun workspace",
                    run_id=context.run_id,
                )
                return
            factual_envelope = FactualEnvelopeBuilder.build(source_packet)
            factual_envelope_text = FactualEnvelopeBuilder.render_for_agent(factual_envelope)

        # Commercial trust boundary: generation may not begin without the
        # authoritative ContentRun. If evidence was supplied, the exact packet
        # and factual envelope are snapshotted on that run before Research starts.
        try:
            if source_packet is None:
                created = await self._persist_required(self.content_runs.create, context, idea)
            else:
                created = await self._persist_required(
                    self.content_runs.create,
                    context,
                    idea,
                    source_packet,
                    factual_envelope,
                )
        except PipelineAbortError:
            yield _sse(
                "pipeline.persistence_failed",
                reason="Authoritative ContentRun could not be persisted",
                run_id=context.run_id,
            )
            return
        if not created:
            logger.error("Authoritative ContentRun repository was unavailable for run %s", context.run_id)
            yield _sse(
                "pipeline.persistence_failed",
                reason="Authoritative ContentRun could not be persisted",
                run_id=context.run_id,
            )
            return
        persistence_active = True

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
                        await self._persist(
                            self.content_runs.mark_stage_started,
                            context.run_id,
                            stage_name,
                            event.model_id,
                            event.provider,
                        )
                        yield _sse(
                            "stage.attempt_started",
                            stage_name=stage_name,
                            model_profile=profile,
                            selected_model=event.model_id,
                            provider=event.provider,
                            attempt_id=event.attempt_id,
                            attempt_number=attempt_number,
                            run_id=context.run_id,
                            event_sequence=event_sequence,
                        )
                    elif isinstance(event, ContentChunk):
                        output_ref[0] += event.text
                        yield _sse(
                            "stage.chunk",
                            stage_name=stage_name,
                            text=event.text,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence,
                        )
                    elif isinstance(event, AttemptResetRequired):
                        yield _sse(
                            "stage.attempt_reset",
                            stage_name=stage_name,
                            reason=event.reason,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence,
                        )
                        output_ref[0] = ""
                    elif isinstance(event, AttemptFailed):
                        await self._persist(self.content_runs.mark_attempt_failed, context.run_id, stage_name, event.reason)
                        yield _sse(
                            "stage.attempt_failed",
                            stage_name=stage_name,
                            reason=event.reason,
                            attempt_id=event.attempt_id,
                            run_id=context.run_id,
                            event_sequence=event_sequence,
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
                            event_sequence=event_sequence,
                        )
                    elif isinstance(event, AttemptCompleted):
                        pass
                    elif isinstance(event, RoutingExhausted):
                        raise Exception(event.reason)

                event_sequence += 1
                await self._persist(self.content_runs.mark_stage_completed, context.run_id, stage_name, output_ref[0])
                yield _sse(
                    "stage.completed",
                    stage_name=stage_name,
                    content=output_ref[0],
                    run_id=context.run_id,
                    event_sequence=event_sequence,
                )
            except Exception as exc:
                event_sequence += 1
                stage_flags["failed"] = True
                await self._persist(
                    self.content_runs.mark_stage_failed,
                    context.run_id,
                    stage_name,
                    str(exc),
                    terminal=not ignore_failure,
                )
                if ignore_failure:
                    yield _sse(f"{stage_name}.failed", reason=str(exc), retryable=True, run_id=context.run_id)
                else:
                    yield _sse(
                        "stage.failed",
                        stage_name=stage_name,
                        reason=str(exc),
                        run_id=context.run_id,
                        event_sequence=event_sequence,
                    )
                    raise PipelineAbortError()

        try:
            def research_stream(ctx):
                if factual_envelope_text is None:
                    return self.research_agent.stream(idea, context=ctx, attempt_id=None)
                return self.research_agent.stream(
                    idea,
                    context=ctx,
                    attempt_id=None,
                    factual_envelope=factual_envelope_text,
                )

            async for event in run_stage(research_stream, "research", self.research_agent.profile.value, research_ref):
                yield event

            def writer_stream(ctx):
                if factual_envelope_text is None:
                    return self.writer_agent.stream(idea, research_ref[0], context=ctx, attempt_id=None)
                return self.writer_agent.stream(
                    idea,
                    research_ref[0],
                    context=ctx,
                    attempt_id=None,
                    factual_envelope=factual_envelope_text,
                )

            async for event in run_stage(writer_stream, "write", self.writer_agent.profile.value, draft_ref):
                yield event

            final_flags = {}

            def edit_stream(ctx):
                if factual_envelope_text is None:
                    return self.editor_agent.stream(draft_ref[0], context=ctx, attempt_id=None)
                return self.editor_agent.stream(
                    draft_ref[0],
                    context=ctx,
                    attempt_id=None,
                    factual_envelope=factual_envelope_text,
                )

            async for event in run_stage(
                edit_stream,
                "edit",
                self.editor_agent.profile.value,
                final_ref,
                stage_flags=final_flags,
            ):
                yield event

            final_status = "NEEDS_LANGUAGE_REVIEW" if final_flags.get("has_validation_warning") else "READY"
        except PipelineAbortError:
            return
        except Exception as exc:
            await self._persist(self.content_runs.mark_failed, context.run_id, "unknown", str(exc))
            yield _sse("stage.failed", stage_name="unknown", reason=str(exc), run_id=context.run_id)
            return

        try:
            await self._persist_required(self.content_runs.mark_text_ready, context.run_id, final_ref[0], final_status)
        except PipelineAbortError:
            yield _sse(
                "pipeline.persistence_failed",
                reason="TEXT_READY lifecycle transition could not be persisted",
                run_id=context.run_id,
            )
            return

        yield _sse(
            "pipeline.text_completed",
            final_status=final_status,
            final_post=final_ref[0],
            run_id=context.run_id,
        )

        visual_status = "FAILED"
        try:
            profile_visual_enabled = True
            if content_profile_snapshot is not None:
                profile_visual_enabled = bool(content_profile_snapshot.get("visual_enabled", True))

            if not profile_visual_enabled:
                visual_status = "SKIPPED"
                yield _sse("visual.prompt_skipped", reason="Disabled by content profile", run_id=context.run_id)
            else:
                yield _sse("visual.prompt_started", run_id=context.run_id)

                def visual_stream(ctx):
                    return self.visual_agent.stream(final_ref[0], context=ctx, attempt_id=None)

                visual_flags = {}
                async for event in run_stage(
                    visual_stream,
                    "visual",
                    self.visual_agent.profile.value,
                    visual_ref,
                    ignore_failure=True,
                    stage_flags=visual_flags,
                ):
                    yield event

                if visual_ref[0] and not visual_flags.get("failed"):
                    visual_status = "READY"
                    yield _sse("visual.prompt_completed", content=visual_ref[0], run_id=context.run_id)
                else:
                    await self._persist(
                        self.content_runs.mark_stage_failed,
                        context.run_id,
                        "visual",
                        "Partial failure or empty output",
                        terminal=False,
                    )
                    yield _sse("visual.prompt_failed", reason="Partial failure or empty output", run_id=context.run_id)
        except Exception as exc:
            await self._persist(
                self.content_runs.mark_stage_failed,
                context.run_id,
                "visual",
                str(exc),
                terminal=False,
            )
            yield _sse("visual.prompt_failed", reason=str(exc), run_id=context.run_id)

        post_id = None
        try:
            db = get_db()
            if db is not None:
                doc = {
                    "run_id": context.run_id,
                    "workspace_id": context.workspace_id,
                    "topic": topic,
                    "style": style,
                    "idea": idea,
                    "content_profile_id": context.content_profile_id,
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
        except Exception as exc:
            logger.warning("Legacy post projection save degraded: %s", exc)

        try:
            await self._persist_required(
                self.content_runs.mark_ready_for_review,
                context.run_id,
                visual_ref[0] if visual_status == "READY" else None,
                post_id,
            )
        except PipelineAbortError:
            yield _sse(
                "pipeline.persistence_failed",
                reason="READY_FOR_REVIEW lifecycle transition could not be persisted",
                run_id=context.run_id,
            )
            return

        # Content Memory is advisory. A memory outage may degrade discovery, but
        # must not replace or rewrite the authoritative ContentRun lifecycle.
        await self._persist(self.content_memory.refresh_review, context.run_id)

        yield _sse(
            "complete",
            run_id=context.run_id,
            content_run_status="READY_FOR_REVIEW",
            persistence_active=persistence_active,
            content_profile_id=context.content_profile_id,
            generation_source_packet_id=source_packet.packet_id if source_packet else None,
            factual_envelope_version=factual_envelope.envelope_version if factual_envelope else None,
            final_status=final_status,
            visual_status=visual_status,
            post_id=post_id,
            final_post=final_ref[0],
            visual_prompt=visual_ref[0] if visual_status == "READY" else None,
        )
