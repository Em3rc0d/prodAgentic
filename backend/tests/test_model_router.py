import pytest
import asyncio
from agents.adapters.types import ModelExecutionError, ErrorCode, ProviderAdapter
from agents.router import ModelRouter, CircuitState, AttemptStarted, ContentChunk, RoutingExhausted, AttemptFailed, AttemptResetRequired, RoutingPolicy
from core.model_registry import ModelProfile, REGISTRY

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
    RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure = True
    
    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.MODEL_NOT_FOUND, "n8n", "gemini-3.6-flash", "attempt-1", 
        404, None, False, True, "Not found"
    )
    
    events = [evt async for evt in router.stream_generation(ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1")]
        
    assert n8n.last_system_instruction == "sys"
    assert router._get_model_breaker("n8n", "gemini-3.6-flash").state == CircuitState.OPEN
    assert router._get_provider_breaker("n8n").state == CircuitState.CLOSED
    assert google.last_system_instruction == "sys"

@pytest.mark.asyncio
async def test_n8n_provider_failure_no_bypass():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure = False
    
    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.SERVICE_UNAVAILABLE, "n8n", "gemini-3.6-flash", "attempt-1", 
        500, None, False, False, "Internal Error"
    )
    
    events = [evt async for evt in router.stream_generation(ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1")]
        
    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    assert isinstance(events[-1], RoutingExhausted)
    assert google.last_system_instruction is None

@pytest.mark.asyncio
async def test_terminal_taxonomy():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    
    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.QUOTA_EXHAUSTED, "n8n", "gemini-3.6-flash", "attempt-1", 
        429, None, False, False, "Quota gone"
    )
    
    events = [evt async for evt in router.stream_generation(ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1")]
    assert isinstance(events[-1], RoutingExhausted)
    assert events[-1].reason == "Terminal error: QUOTA_EXHAUSTED"

@pytest.mark.asyncio
async def test_circuit_breaker_half_open():
    from agents.router import CircuitBreaker
    cb = CircuitBreaker()
    cb.record_failure("test", ttl_seconds=-1) # Immediate expire
    assert cb.state == CircuitState.OPEN
    
    # First allowed probe
    assert cb.is_allowed() is True
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._half_open_probe_active is True
    
    # Second probe should be rejected
    assert cb.is_allowed() is False
