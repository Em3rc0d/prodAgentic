from agents.router import CircuitState, ModelRouter, RoutingPolicy
from routes.batches import (
    R4_PLANNING_ATTEMPT_SECONDS,
    R4_PLANNING_FALLBACK_RESERVE_SECONDS,
    R4_PLANNING_STAGE_SECONDS,
    _planning_router,
)
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


def test_planning_router_expands_only_the_isolated_planning_budget():
    google = StubAdapter()
    policy = RoutingPolicy(
        max_stage_seconds=75.0,
        per_attempt_seconds=25.0,
        minimum_fallback_seconds=10.0,
        max_total_attempts=5,
        allow_direct_provider_fallback_after_n8n_failure=True,
    )
    shared = ModelRouter(google_adapter=google, routing_policy=policy)

    planning = _planning_router(shared)

    assert planning is not shared
    assert planning.google_adapter is google
    assert planning.policy is not shared.policy
    assert planning.policy.max_stage_seconds == R4_PLANNING_STAGE_SECONDS == 120.0
    assert planning.policy.per_attempt_seconds == R4_PLANNING_ATTEMPT_SECONDS == 60.0
    assert planning.policy.minimum_fallback_seconds == R4_PLANNING_FALLBACK_RESERVE_SECONDS == 15.0
    assert planning.policy.max_total_attempts == policy.max_total_attempts
    assert planning.policy.allow_direct_provider_fallback_after_n8n_failure is True

    assert shared.policy.max_stage_seconds == 75.0
    assert shared.policy.per_attempt_seconds == 25.0
    assert shared.policy.minimum_fallback_seconds == 10.0
