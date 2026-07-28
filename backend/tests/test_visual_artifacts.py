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

@pytest.mark.asyncio
async def test_visual_uses_image_prompt_language():
    adapter = MockAdapter([["A cyberpunk city scene"]])
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
