from agents.router import CircuitState, ModelRouter, RoutingPolicy
from routes.production import _isolated_router


class StubAdapter:
    pass


def test_production_router_breakers_are_isolated_per_content_request():
    google = StubAdapter()
    policy = RoutingPolicy(max_total_attempts=5)
    shared = ModelRouter(google_adapter=google, routing_policy=policy)

    first = _isolated_router(shared)
    second = _isolated_router(shared)

    first._get_model_breaker("google", "gemini-3.6-flash").record_failure("SERVICE_UNAVAILABLE")
    first._get_provider_breaker("google").record_failure("SERVICE_UNAVAILABLE")

    assert first._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.OPEN
    assert second._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.CLOSED
    assert shared._get_model_breaker("google", "gemini-3.6-flash").state == CircuitState.CLOSED

    assert second._get_provider_breaker("google").state == CircuitState.CLOSED
    assert shared._get_provider_breaker("google").state == CircuitState.CLOSED
    assert first.google_adapter is google
    assert second.google_adapter is google
    assert first.policy is policy
    assert second.policy is policy
