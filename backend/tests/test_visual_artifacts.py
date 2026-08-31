import pytest
from core.context import GenerationContext, LanguageCode
from core.validator import ArtifactType, LanguageValidator, ValidationStatus
from agents.router import ModelRouter, ModelExecutionRequest, RoutingPolicy, AttemptCompleted, ContentChunk
from agents.adapters.types import ProviderAdapter, ModelExecutionError, ErrorCode
from core.model_registry import ModelProfile


class MockAdapter(ProviderAdapter):
    def __init__(self, sequence):
        self.sequence = sequence
        self.call_count = 0

    async def stream(self, model, prompt, system_instruction, attempt_id, run_id, profile_name):
        self.call_count += 1
        current_seq = self.sequence[self.call_count - 1]

        if isinstance(current_seq, Exception):
            raise current_seq

        for chunk in current_seq:
            yield "chunk", chunk


class AuthoritativeContentRunStub:
    """Minimal durable-lifecycle stub for orchestrator contract tests.

    Commercial V1 intentionally fails generation closed when the authoritative
    ContentRun cannot be created or transitioned. Visual sequencing tests are
    not persistence-failure tests, so they must provide that authority explicitly
    rather than relying on the pre-hardening `None` repository behavior.
    """

    async def create(self, *args, **kwargs):
        return True

    async def mark_stage_started(self, *args, **kwargs):
        return True

    async def mark_attempt_failed(self, *args, **kwargs):
        return True

    async def mark_stage_completed(self, *args, **kwargs):
        return True

    async def mark_stage_failed(self, *args, **kwargs):
        return True

    async def mark_failed(self, *args, **kwargs):
        return True

    async def mark_text_ready(self, *args, **kwargs):
        return True

    async def mark_ready_for_review(self, *args, **kwargs):
        return True


@pytest.mark.asyncio
async def test_visual_uses_image_prompt_language():
    # Make the text longer to pass confidence thresholds
    adapter = MockAdapter([["A cyberpunk city scene with tall neon buildings and flying cars, extremely detailed and cinematic"]])
    router = ModelRouter(google_adapter=adapter)

    ctx = GenerationContext(
        run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.EN, source_detection_confidence=0.0,
        requested_target_language=LanguageCode.ES, resolved_target_language=LanguageCode.ES, image_prompt_language=LanguageCode.EN
    )
    request = ModelExecutionRequest(
        context=ctx, model_profile=ModelProfile.ECONOMY_TEXT, artifact_type=ArtifactType.VISUAL,
        system_instruction="Base instruction", user_prompt="prompt", expected_output_language=LanguageCode.EN
    )

    events = [e async for e in router.stream_generation(request)]

    assert any(isinstance(e, AttemptCompleted) for e in events)
    text = "".join([e.text for e in events if isinstance(e, ContentChunk)])
    val = LanguageValidator.validate(text, LanguageCode.EN, ArtifactType.VISUAL)
    assert val.status == ValidationStatus.MATCH


@pytest.mark.asyncio
async def test_text_completed_precedes_visual_started():
    import json
    from agents.orchestrator import PipelineOrchestrator

    # Mocking agents to just yield AttemptCompleted
    class MockAgent:
        def __init__(self, profile):
            self.profile = ModelProfile(profile)

        async def stream(self, *args, **kwargs):
            from agents.router import AttemptCompleted
            yield AttemptCompleted("attempt-1")

    orchestrator = PipelineOrchestrator(None)
    orchestrator.content_runs = AuthoritativeContentRunStub()
    orchestrator.research_agent = MockAgent(ModelProfile.ECONOMY_TEXT.value)
    orchestrator.writer_agent = MockAgent(ModelProfile.ECONOMY_TEXT.value)
    orchestrator.editor_agent = MockAgent(ModelProfile.QUALITY_TEXT.value)
    orchestrator.visual_agent = MockAgent(ModelProfile.ECONOMY_TEXT.value)

    events = [e async for e in orchestrator.run_pipeline_stream("idea", "topic", "style")]

    parsed_events = [json.loads(e["data"]) for e in events]

    text_completed_idx = next(i for i, e in enumerate(parsed_events) if e.get("stage") == "pipeline.text_completed")
    visual_started_idx = next(i for i, e in enumerate(parsed_events) if e.get("stage") == "visual.prompt_started")

    assert text_completed_idx < visual_started_idx
    assert parsed_events[text_completed_idx]["final_status"] == "READY"


@pytest.mark.asyncio
async def test_partial_visual_output_never_becomes_ready():
    import json
    from agents.orchestrator import PipelineOrchestrator

    class MockAgent:
        def __init__(self, profile):
            self.profile = ModelProfile(profile)

        async def stream(self, *args, **kwargs):
            from agents.router import AttemptCompleted
            yield AttemptCompleted("attempt-1")

    class FailingVisualAgent:
        def __init__(self):
            self.profile = ModelProfile.ECONOMY_TEXT

        async def stream(self, *args, **kwargs):
            from agents.router import ContentChunk
            yield ContentChunk("partial text", "attempt-1")
            raise Exception("Provider failed mid-stream")

    orchestrator = PipelineOrchestrator(None)
    orchestrator.content_runs = AuthoritativeContentRunStub()
    orchestrator.research_agent = MockAgent(ModelProfile.ECONOMY_TEXT.value)
    orchestrator.writer_agent = MockAgent(ModelProfile.ECONOMY_TEXT.value)
    orchestrator.editor_agent = MockAgent(ModelProfile.QUALITY_TEXT.value)
    orchestrator.visual_agent = FailingVisualAgent()

    events = [e async for e in orchestrator.run_pipeline_stream("idea", "topic", "style")]
    parsed_events = [json.loads(e["data"]) for e in events]

    complete_event = next(e for e in parsed_events if e.get("stage") == "complete")
    assert complete_event["visual_status"] == "FAILED"
    assert complete_event["final_status"] == "READY"

    visual_failed_event = next(e for e in parsed_events if e.get("stage") == "visual.prompt_failed")
    assert "Partial failure" in visual_failed_event["reason"]
