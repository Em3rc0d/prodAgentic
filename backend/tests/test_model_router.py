import pytest

from agents.adapters.types import ErrorCode, ModelExecutionError, ProviderAdapter
from agents.router import (
    AttemptCompleted,
    AttemptFailed,
    AttemptResetRequired,
    AttemptStarted,
    CircuitState,
    ModelExecutionRequest,
    ModelRouter,
    RoutingExhausted,
    RoutingPolicy,
)
from core.context import GenerationContext, LanguageCode
from core.model_registry import ModelProfile, REGISTRY
from core.validator import ArtifactType


ctx = GenerationContext(
    run_id="run-1",
    topic="",
    style="",
    requested_source_language=LanguageCode.AUTO,
    detected_source_language=LanguageCode.EN,
    source_detection_confidence=0.0,
    requested_target_language=LanguageCode.EN,
    resolved_target_language=LanguageCode.EN,
    image_prompt_language=LanguageCode.EN,
)


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


def _request() -> ModelExecutionRequest:
    return ModelExecutionRequest(
        context=ctx,
        model_profile=ModelProfile.QUALITY_TEXT,
        artifact_type=ArtifactType.FINAL,
        system_instruction="sys",
        user_prompt="prompt",
        expected_output_language=LanguageCode.EN,
    )


def test_quality_profile_configures_three_ordered_model_routes():
    models = REGISTRY[ModelProfile.QUALITY_TEXT]
    assert [model.model_id for model in models] == [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]


@pytest.mark.asyncio
async def test_router_circuit_breaker_isolation():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    router.policy.allow_direct_provider_fallback_after_n8n_failure = True

    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.MODEL_NOT_FOUND,
        "n8n",
        "gemini-3.6-flash",
        "attempt-1",
        404,
        None,
        False,
        True,
        "Not found",
    )

    events = [evt async for evt in router.stream_generation(_request())]

    assert events
    assert n8n.last_system_instruction == "sys"
    assert router._get_model_breaker("n8n", "gemini-3.6-flash").state == CircuitState.OPEN
    assert router._get_provider_breaker("n8n").state == CircuitState.CLOSED
    assert google.last_system_instruction == "sys"


@pytest.mark.asyncio
async def test_n8n_provider_failure_no_bypass():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)
    router.policy.allow_direct_provider_fallback_after_n8n_failure = False

    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.SERVICE_UNAVAILABLE,
        "n8n",
        "gemini-3.6-flash",
        "attempt-1",
        500,
        None,
        False,
        False,
        "Internal Error",
    )

    events = [evt async for evt in router.stream_generation(_request())]

    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    assert isinstance(events[-1], RoutingExhausted)
    assert google.last_system_instruction is None


@pytest.mark.asyncio
async def test_n8n_quota_keeps_provider_no_bypass_policy():
    google = MockAdapter("google")
    n8n = MockAdapter("n8n")
    router = ModelRouter(google, n8n)

    n8n.should_fail = True
    n8n.fail_error = ModelExecutionError(
        ErrorCode.QUOTA_EXHAUSTED,
        "n8n",
        "gemini-3.6-flash",
        "attempt-1",
        429,
        None,
        False,
        False,
        "Quota gone",
    )

    events = [evt async for evt in router.stream_generation(_request())]
    assert isinstance(events[-1], RoutingExhausted)
    assert events[-1].reason == "n8n provider quota exhausted and bypass is disabled"
    assert router._get_provider_breaker("n8n").state == CircuitState.OPEN
    assert google.last_system_instruction is None


@pytest.mark.asyncio
@pytest.mark.parametrize("all_exhausted", [False, True])
async def test_google_quota_is_route_scoped_and_attempts_are_bounded(monkeypatch, all_exhausted):
    models = REGISTRY[ModelProfile.QUALITY_TEXT]
    monkeypatch.setattr("agents.router.get_models_for_profile", lambda _: models)
    calls = []

    class QuotaAdapter(ProviderAdapter):
        async def stream(self, model, prompt, **kwargs):
            calls.append(model)
            if all_exhausted or model == models[0].model_id:
                raise ModelExecutionError(
                    ErrorCode.QUOTA_EXHAUSTED, "google", model, kwargs["attempt_id"],
                    429, "RESOURCE_EXHAUSTED", False, True, "provider-private-detail",
                )
            yield ("chunk", "A short reply.")

    router = ModelRouter(QuotaAdapter())
    events = [event async for event in router.stream_generation(_request())]
    assert calls == [model.model_id for model in models[:2]]
    assert router._get_model_breaker("google", models[0].model_id).state == CircuitState.OPEN
    assert router._get_provider_breaker("google").state == CircuitState.CLOSED
    failures = [event for event in events if isinstance(event, AttemptFailed)]
    assert all(event.failure_code == "QUOTA_EXHAUSTED" for event in failures)
    assert "provider-private-detail" not in repr(events)
    assert isinstance(events[-1], RoutingExhausted if all_exhausted else AttemptCompleted)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open():
    from agents.router import CircuitBreaker

    cb = CircuitBreaker()
    cb.record_failure("test", ttl_seconds=-1)
    assert cb.state == CircuitState.OPEN
    assert cb.is_allowed() is True
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._half_open_probe_active is True
    assert cb.is_allowed() is False


@pytest.mark.asyncio
async def test_google_503_uses_independent_lite_fallback_model():
    policy = RoutingPolicy(allow_direct_provider_fallback_after_n8n_failure=True)

    class FailPrimaryGoogle(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            self.last_system_instruction = kwargs.get("system_instruction")
            if model == "gemini-3.6-flash":
                raise ModelExecutionError(
                    ErrorCode.SERVICE_UNAVAILABLE,
                    "google",
                    model,
                    "attempt-1",
                    503,
                    None,
                    True,
                    False,
                    "Unavailable",
                )
            yield ("chunk", f"hello from {model}")

    google = FailPrimaryGoogle("google")
    router = ModelRouter(google, None, routing_policy=policy)

    events = [evt async for evt in router.stream_generation(_request())]

    assert router._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.OPEN
    fallback_started = next(
        (
            event
            for event in events
            if isinstance(event, AttemptStarted)
            and event.model_id == "gemini-3.5-flash-lite"
            and event.provider == "google"
        ),
        None,
    )
    assert fallback_started is not None
    assert any(
        isinstance(event, AttemptCompleted) and event.attempt_id == fallback_started.attempt_id
        for event in events
    )
    assert not any(isinstance(event, RoutingExhausted) for event in events)


@pytest.mark.asyncio
async def test_google_midstream_failure_resets_and_switches_tier():
    policy = RoutingPolicy(allow_direct_provider_fallback_after_n8n_failure=True)

    class MidstreamFailGoogle(MockAdapter):
        async def stream(self, model: str, prompt: str, **kwargs):
            self.last_system_instruction = kwargs.get("system_instruction")
            if model == "gemini-3.6-flash":
                yield ("chunk", "First part of the stream")
                raise ModelExecutionError(
                    ErrorCode.SERVICE_UNAVAILABLE,
                    "google",
                    model,
                    "attempt-1",
                    503,
                    None,
                    True,
                    False,
                    "Failed halfway",
                )
            yield ("chunk", f"hello from {model}")

    google = MidstreamFailGoogle("google")
    router = ModelRouter(google, None, routing_policy=policy)

    events = [evt async for evt in router.stream_generation(_request())]

    assert any(isinstance(event, AttemptResetRequired) for event in events)
    assert router._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.OPEN
    fallback_started = next(
        (
            event
            for event in events
            if isinstance(event, AttemptStarted)
            and event.model_id == "gemini-3.5-flash-lite"
            and event.provider == "google"
        ),
        None,
    )
    assert fallback_started is not None
    assert any(
        isinstance(event, AttemptCompleted) and event.attempt_id == fallback_started.attempt_id
        for event in events
    )
    assert not any(isinstance(event, RoutingExhausted) for event in events)


@pytest.mark.asyncio
async def test_router_never_calls_none_adapter():
    google = MockAdapter("google")
    router = ModelRouter(google, None, routing_policy=RoutingPolicy())

    adapters = dict(router._get_adapters())
    assert "n8n" not in adapters
    assert "google" in adapters

    router2 = ModelRouter(None, None, routing_policy=RoutingPolicy())
    assert not router2._get_adapters()

    events = [evt async for evt in router2.stream_generation(_request())]
    assert len(events) == 1
    assert isinstance(events[0], RoutingExhausted)
    assert "No viable provider" in events[0].reason
