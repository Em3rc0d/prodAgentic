import pytest
import asyncio
from agents.idea_generator import IdeaGeneratorAgent, GenerationIdeasFailed
from agents.router import AttemptStarted, ContentChunk, AttemptCompleted, RoutingExhausted
from core.model_registry import ModelProfile
from core.context import GenerationContext, LanguageCode

class MockRouter:
    def __init__(self, output_chunks=None, fail_with=None):
        self.output_chunks = output_chunks or []
        self.fail_with = fail_with

    async def stream_generation(self, request):
        if self.fail_with:
            yield RoutingExhausted(self.fail_with)
            return
            
        yield AttemptStarted("model-1", "attempt-1", "google")
        for chunk in self.output_chunks:
            yield ContentChunk(chunk, "attempt-1")
        yield AttemptCompleted("attempt-1")

@pytest.mark.asyncio
async def test_idea_generator_valid_output():
    json_output = '["Idea 1", "Idea 2", "Idea 3", "Idea 4", "Idea 5", "Idea 6", "Idea 7"]'
    router = MockRouter(output_chunks=[json_output])
    agent = IdeaGeneratorAgent(router)
    
    ctx = GenerationContext(run_id="run-1", topic="topic", style="style", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)
    ideas = await agent.generate_ideas(ctx)
    assert len(ideas) == 7
    assert ideas[0] == "Idea 1"

@pytest.mark.asyncio
async def test_idea_generator_invalid_json():
    router = MockRouter(output_chunks=['["Idea 1", ']) # Broken JSON
    agent = IdeaGeneratorAgent(router)
    
    ctx = GenerationContext(run_id="run-1", topic="topic", style="style", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas(ctx)
    assert "JSON parsing error" in str(exc.value)

@pytest.mark.asyncio
async def test_idea_generator_wrong_count():
    json_output = '["Idea 1", "Idea 2"]' # Only 2
    router = MockRouter(output_chunks=[json_output])
    agent = IdeaGeneratorAgent(router)
    
    ctx = GenerationContext(run_id="run-1", topic="topic", style="style", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas(ctx)
    assert "Expected 7 valid ideas" in str(exc.value)

@pytest.mark.asyncio
async def test_idea_generator_routing_exhausted():
    router = MockRouter(fail_with="All failed")
    agent = IdeaGeneratorAgent(router)
    
    ctx = GenerationContext(run_id="run-1", topic="topic", style="style", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas(ctx)
    assert "Failed to generate ideas: All failed" in str(exc.value)
