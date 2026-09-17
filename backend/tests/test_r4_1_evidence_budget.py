from agents.router import ModelRouter, RoutingPolicy
from routes.production import (
    R4_EVIDENCE_ATTEMPT_SECONDS,
    R4_EVIDENCE_STAGE_SECONDS,
    _evidence_router,
)


class StubAdapter:
    pass


def test_evidence_router_expands_only_the_isolated_evidence_budget():
    google = StubAdapter()
    policy = RoutingPolicy(
        max_stage_seconds=75.0,
        per_attempt_seconds=25.0,
        minimum_fallback_seconds=10.0,
        max_total_attempts=5,
        allow_direct_provider_fallback_after_n8n_failure=True,
    )
    shared = ModelRouter(google_adapter=google, routing_policy=policy)

    evidence = _evidence_router(shared)

    assert evidence is not shared
    assert evidence.google_adapter is google
    assert evidence.policy is not shared.policy
    assert evidence.policy.max_stage_seconds == R4_EVIDENCE_STAGE_SECONDS == 60.0
    assert evidence.policy.per_attempt_seconds == R4_EVIDENCE_ATTEMPT_SECONDS == 60.0
    assert evidence.policy.minimum_fallback_seconds == policy.minimum_fallback_seconds
    assert evidence.policy.max_total_attempts == policy.max_total_attempts
    assert evidence.policy.allow_direct_provider_fallback_after_n8n_failure is True

    assert shared.policy.max_stage_seconds == 75.0
    assert shared.policy.per_attempt_seconds == 25.0
    assert shared.policy.minimum_fallback_seconds == 10.0
