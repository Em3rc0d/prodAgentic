import pytest
import asyncio
from agents.idea_generator import IdeaGeneratorAgent, GenerationIdeasFailed
from agents.router import AttemptStarted, ContentChunk, AttemptCompleted, RoutingExhausted
from core.model_registry import ModelProfile

class MockRouter:
    def __init__(self, output_chunks=None, fail_with=None):
        self.output_chunks = output_chunks or []
        self.fail_with = fail_with

    async def stream_generation(self, profile, sys, prompt, run_id):
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
    
    ideas = await agent.generate_ideas("topic", "style")
    assert len(ideas) == 7
    assert ideas[0] == "Idea 1"

@pytest.mark.asyncio
async def test_idea_generator_invalid_json():
    router = MockRouter(output_chunks=['["Idea 1", ']) # Broken JSON
    agent = IdeaGeneratorAgent(router)
    
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas("topic", "style")
    assert "JSON parsing error" in str(exc.value)

@pytest.mark.asyncio
async def test_idea_generator_wrong_count():
    json_output = '["Idea 1", "Idea 2"]' # Only 2
    router = MockRouter(output_chunks=[json_output])
    agent = IdeaGeneratorAgent(router)
    
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas("topic", "style")
    assert "Expected 7 valid ideas" in str(exc.value)

@pytest.mark.asyncio
async def test_idea_generator_routing_exhausted():
    router = MockRouter(fail_with="All failed")
    agent = IdeaGeneratorAgent(router)
    
    with pytest.raises(GenerationIdeasFailed) as exc:
        await agent.generate_ideas("topic", "style")
    assert "Failed to generate ideas: All failed" in str(exc.value)
