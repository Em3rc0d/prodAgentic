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
        self.requested_models = []
        self.requested_attempts = []

    async def stream(self, model, prompt, system_instruction, attempt_id, run_id, profile_name):
        self.call_count += 1
        self.last_system_instruction = system_instruction
        self.requested_models.append(model)
        self.requested_attempts.append(attempt_id)
        
        if self.call_count > len(self.sequence):
            return
        current_seq = self.sequence[self.call_count - 1]
        
        if isinstance(current_seq, Exception):
            raise current_seq
            
        for chunk in current_seq:
            yield "chunk", chunk

@pytest.mark.asyncio
async def test_first_mismatch_adds_repair_instruction():
    # Make the English and Spanish texts longer to bypass CONFIDENCE thresholds
    adapter = MockAdapter([["This is English text that is quite long and confidently detected as English."], ["Esto es español y también es suficientemente largo para ser detectado con mucha confianza."]])
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
    assert adapter.requested_models[0] == adapter.requested_models[1]

@pytest.mark.asyncio
async def test_second_mismatch_changes_route():
    # English -> English -> Spanish. The second English will exhaust repairs and open circuit.
    adapter = MockAdapter([
        ["This is English text that is quite long and confidently detected as English (Attempt 1)."], 
        ["This is English text that is quite long and confidently detected as English (Attempt 2)."], 
        ["Esto es español y también es suficientemente largo para ser detectado con mucha confianza."]
    ])
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
    # The first two attempts should be on the same model (due to repair)
    assert adapter.requested_models[0] == adapter.requested_models[1]
    # The third attempt should be on a DIFFERENT model because the circuit opened
    assert adapter.requested_models[1] != adapter.requested_models[2]
    # The third attempt should have a new attempt_id
    assert adapter.requested_attempts[1] != adapter.requested_attempts[2]
    
    assert not any(isinstance(e, RoutingExhausted) for e in events)
