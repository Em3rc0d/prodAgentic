import pytest
import asyncio
from agents.adapters.types import ModelExecutionError, ErrorCode, ProviderAdapter
from agents.router import ModelRouter, CircuitState, AttemptStarted, ContentChunk, RoutingExhausted
from core.model_registry import ModelProfile

class MockAdapter(ProviderAdapter):
    def __init__(self, name="mock"):
        self.name = name
        self.should_fail = False
        self.fail_error = None
        self.last_system_instruction = None

    async def stream(self, model: str, prompt: str, **kwargs):
        self.last_system_instruction = kwargs.get("system_instruction")
        if self.should_fail:
            raise self.fail_error
        yield ("chunk", f"hello from {model}")

@pytest.mark.asyncio
async def test_router_circuit_breaker_isolation():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    router.allow_direct_provider_fallback_after_n8n_failure = True
    
    # Force n8n to fail with MODEL_NOT_FOUND
    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.MODEL_NOT_FOUND, "n8n", "gemini-3.6-flash", "attempt-1", 
        404, None, False, True, "Not found"
    )
    
    events = []
    async for evt in router.stream_generation(ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1"):
        events.append(evt)
        
    assert n8n.last_system_instruction == "sys"
    # Model breaker for n8n should be OPEN
    assert router._get_model_breaker("n8n", "gemini-3.6-flash").state == CircuitState.OPEN
    # But Provider breaker for n8n should be CLOSED
    assert router._get_provider_breaker("n8n").state == CircuitState.CLOSED
    
    # Since n8n model failed, it should have moved to google
    assert google.last_system_instruction == "sys"

@pytest.mark.asyncio
async def test_n8n_provider_failure_no_bypass():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    router.allow_direct_provider_fallback_after_n8n_failure = False
    
    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.SERVICE_UNAVAILABLE, "n8n", "gemini-3.6-flash", "attempt-1", 
        500, None, False, False, "Internal Error"
    )
    
    events = []
    async for evt in router.stream_generation(ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1"):
        events.append(evt)
        
    # Provider breaker for n8n should be OPEN
    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    
    # Should have yielded RoutingExhausted since bypass is False
    assert isinstance(events[-1], RoutingExhausted)
    
    # Google should NOT have been called
    assert google.last_system_instruction is None
