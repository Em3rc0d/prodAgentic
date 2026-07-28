import pytest
from core.context import GenerationContext, LanguageCode
from core.validator import ArtifactType
from core.model_registry import ModelProfile
from agents.router import ModelRouter, ModelExecutionRequest, RoutingPolicy, AttemptFailed, AttemptResetRequired, ContentChunk, RoutingExhausted
from agents.adapters.types import ProviderAdapter, ModelExecutionError, ErrorCode

class MockAdapter(ProviderAdapter):
    def __init__(self, sequence):
        self.sequence = sequence
        self.call_count = 0
        self.last_system_instruction = None

    async def stream(self, model, prompt, system_instruction, attempt_id, run_id, profile_name):
        self.call_count += 1
        self.last_system_instruction = system_instruction
        if self.call_count > len(self.sequence):
            return
        current_seq = self.sequence[self.call_count - 1]
        
        if isinstance(current_seq, Exception):
            raise current_seq
            
        for chunk in current_seq:
            yield "chunk", chunk

@pytest.mark.asyncio
async def test_first_mismatch_adds_repair_instruction():
    adapter = MockAdapter([["This is English"], ["Esto es español"]])
    router = ModelRouter(google_adapter=adapter)
    
    ctx = GenerationContext(
        run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, 
        detected_source_language=LanguageCode.EN, source_detection_confidence=0.0,
        requested_target_language=LanguageCode.ES, resolved_target_language=LanguageCode.ES, image_prompt_language=LanguageCode.EN
    )
    request = ModelExecutionRequest(
        context=ctx, model_profile=ModelProfile.ECONOMY_TEXT, artifact_type=ArtifactType.FINAL,
        system_instruction="Base instruction", user_prompt="prompt", expected_output_language=LanguageCode.ES
    )
    
    events = [e async for e in router.stream_generation(request)]
    
    assert adapter.call_count == 2
    assert "The previous response violated the language contract." in adapter.last_system_instruction
    assert any(isinstance(e, AttemptResetRequired) for e in events)

@pytest.mark.asyncio
async def test_second_mismatch_changes_route():
    adapter = MockAdapter([["This is English 1"], ["This is English 2"], ["Esto es español"]])
    router = ModelRouter(google_adapter=adapter)
    
    ctx = GenerationContext(
        run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, 
        detected_source_language=LanguageCode.EN, source_detection_confidence=0.0,
        requested_target_language=LanguageCode.ES, resolved_target_language=LanguageCode.ES, image_prompt_language=LanguageCode.EN
    )
    request = ModelExecutionRequest(
        context=ctx, model_profile=ModelProfile.ECONOMY_TEXT, artifact_type=ArtifactType.FINAL,
        system_instruction="Base instruction", user_prompt="prompt", expected_output_language=LanguageCode.ES
    )
    
    events = [e async for e in router.stream_generation(request)]
    
    assert adapter.call_count == 3
    assert not any(isinstance(e, RoutingExhausted) for e in events)
