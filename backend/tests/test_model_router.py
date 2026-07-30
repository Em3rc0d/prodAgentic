from core.context import GenerationContext, LanguageCode
ctx = GenerationContext(run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)
import pytest
import asyncio
from agents.adapters.types import ModelExecutionError, ErrorCode, ProviderAdapter
from agents.router import ModelRouter, CircuitState, AttemptStarted, ContentChunk, RoutingExhausted, AttemptFailed, AttemptResetRequired, RoutingPolicy, AttemptCompleted
from core.model_registry import ModelProfile
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest

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
    
    events = [evt async for evt in router.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
        
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
    
    events = [evt async for evt in router.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
        
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
    
    events = [evt async for evt in router.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
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

@pytest.mark.asyncio
async def test_google_503_uses_fallback_model():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    from agents.router import RoutingPolicy
    # Use production policy with max_total_attempts=4 but enable bypass
    policy = RoutingPolicy(allow_direct_provider_fallback_after_n8n_failure=True)
    router = ModelRouter(google, n8n, routing_policy=policy)
    
    class FailOnceGoogle(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            if model == "gemini-3.6-flash":
                raise ModelExecutionError(
                    ErrorCode.SERVICE_UNAVAILABLE, "google", model, "attempt-1", 503, None, True, False, "Unavailable"
                )
            yield ("chunk", f"hello from {model}")

    class FailN8n(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            raise ModelExecutionError(
                ErrorCode.SERVICE_UNAVAILABLE, "n8n", model, "attempt-n8n", 503, None, True, False, "Unavailable"
            )
            yield

    router.google_adapter = FailOnceGoogle("google")
    router.n8n_adapter = FailN8n("n8n")

    events = [evt async for evt in router.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
    
    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    assert router._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.OPEN
    
    fallback_started = next((e for e in events if isinstance(e, AttemptStarted) and e.model_id == "gemini-3.5-flash" and e.provider == "google"), None)
    assert fallback_started is not None
    
    assert any(isinstance(e, AttemptCompleted) and e.attempt_id == fallback_started.attempt_id for e in events)
    assert not any(isinstance(e, RoutingExhausted) for e in events)

@pytest.mark.asyncio
async def test_google_midstream_failure_resets_and_switches_model():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    from agents.router import RoutingPolicy
    policy = RoutingPolicy(allow_direct_provider_fallback_after_n8n_failure=True)
    router = ModelRouter(google, n8n, routing_policy=policy)
    
    class MidstreamFailGoogle(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            if model == "gemini-3.6-flash":
                yield ("chunk", "First part of the stream")
                raise ModelExecutionError(
                    ErrorCode.SERVICE_UNAVAILABLE, "google", model, "attempt-1", 503, None, True, False, "Failed halfway"
                )
            yield ("chunk", f"hello from {model}")

    class FailN8n(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            raise ModelExecutionError(
                ErrorCode.SERVICE_UNAVAILABLE, "n8n", model, "attempt-n8n", 503, None, True, False, "Unavailable"
            )
            yield

    router.google_adapter = MidstreamFailGoogle("google")
    router.n8n_adapter = FailN8n("n8n")

    events = [evt async for evt in router.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
    
    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    assert any(isinstance(evt, AttemptResetRequired) for evt in events)
    assert router._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.OPEN
    
    fallback_started = next((e for e in events if isinstance(e, AttemptStarted) and e.model_id == "gemini-3.5-flash" and e.provider == "google"), None)
    assert fallback_started is not None
    
    assert any(isinstance(e, AttemptCompleted) and e.attempt_id == fallback_started.attempt_id for e in events)
    assert not any(isinstance(e, RoutingExhausted) for e in events)

@pytest.mark.asyncio
async def test_router_never_calls_none_adapter():
    google = MockAdapter("google")
    from agents.router import RoutingPolicy
    router = ModelRouter(google, None, routing_policy=RoutingPolicy())
    
    adapters = dict(router._get_adapters())
    assert "n8n" not in adapters
    assert "google" in adapters
    
    router2 = ModelRouter(None, None, routing_policy=RoutingPolicy())
    assert not router2._get_adapters()
    
    events = [evt async for evt in router2.stream_generation(ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN))]
    assert len(events) == 1
    assert isinstance(events[0], RoutingExhausted)
    assert "No viable provider" in events[0].reason
