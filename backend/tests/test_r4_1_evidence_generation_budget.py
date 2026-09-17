from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.router import ModelRouter, RoutingPolicy
from infrastructure.evidence import google_grounding
from infrastructure.evidence.google_grounding import (
    EVIDENCE_MAX_ATTEMPTS_PER_MODEL,
    EVIDENCE_MAX_FINDINGS,
    EVIDENCE_MAX_OUTPUT_TOKENS,
    EVIDENCE_SINGLE_ATTEMPT_SECONDS,
    GoogleGroundingEvidenceProvider,
)


@pytest.mark.asyncio
async def test_grounded_evidence_uses_bounded_generation_envelope(monkeypatch):
    captured = {}

    class Models:
        async def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(candidates=[])

    adapter = SimpleNamespace(
        async_client=SimpleNamespace(models=Models()),
        _translate_error=lambda exc, model, run_id: exc,
    )
    router = ModelRouter(
        google_adapter=adapter,
        routing_policy=RoutingPolicy(
            max_models_per_stage=1,
            max_stage_seconds=2.0,
            per_attempt_seconds=2.0,
            minimum_fallback_seconds=0.0,
        ),
    )

    monkeypatch.setattr(
        google_grounding,
        "get_models_for_profile",
        lambda profile: [SimpleNamespace(model_id="grounded-search-model")],
    )
    monkeypatch.setattr(google_grounding, "plan_sha256", lambda plan: "a" * 64)

    plan = SimpleNamespace(
        plan_id="plan-1",
        canonical_topic="distributed systems",
        angle="practical tradeoffs",
        subtopics=("latency", "reliability"),
    )

    bundle = await GoogleGroundingEvidenceProvider(router).acquire(
        tenant_id="tenant-1",
        run_id="run-1",
        plan=plan,
        profile=SimpleNamespace(),
    )

    assert bundle.plan_id == "plan-1"
    assert captured["model"] == "grounded-search-model"
    assert captured["config"].max_output_tokens == EVIDENCE_MAX_OUTPUT_TOKENS == 768
    assert EVIDENCE_MAX_FINDINGS == 6
    assert EVIDENCE_MAX_ATTEMPTS_PER_MODEL == 2
    assert EVIDENCE_SINGLE_ATTEMPT_SECONDS == 55.0
    assert "at most 6 concise one-sentence factual findings" in captured["contents"]
    assert len(captured["config"].tools) == 1
    assert captured["config"].tools[0].google_search is not None


@pytest.mark.asyncio
async def test_grounded_evidence_retries_same_model_after_bounded_timeout(monkeypatch):
    calls = 0

    class Models:
        async def generate_content(self, *, model, contents, config):
            nonlocal calls
            calls += 1
            if calls == 1:
                await google_grounding.asyncio.sleep(0.06)
            return SimpleNamespace(candidates=[])

    adapter = SimpleNamespace(
        async_client=SimpleNamespace(models=Models()),
        _translate_error=lambda exc, model, run_id: exc,
    )
    router = ModelRouter(
        google_adapter=adapter,
        routing_policy=RoutingPolicy(
            max_models_per_stage=1,
            max_stage_seconds=1.0,
            per_attempt_seconds=1.0,
            minimum_fallback_seconds=0.0,
        ),
    )

    monkeypatch.setattr(
        google_grounding,
        "get_models_for_profile",
        lambda profile: [SimpleNamespace(model_id="grounded-search-model")],
    )
    monkeypatch.setattr(google_grounding, "plan_sha256", lambda plan: "b" * 64)
    monkeypatch.setattr(google_grounding, "EVIDENCE_SINGLE_ATTEMPT_SECONDS", 0.05)
    monkeypatch.setattr(google_grounding, "EVIDENCE_RETRY_DELAY_SECONDS", 0.0)

    plan = SimpleNamespace(
        plan_id="plan-2",
        canonical_topic="reliable systems",
        angle="failure recovery",
        subtopics=("timeouts",),
    )

    bundle = await GoogleGroundingEvidenceProvider(router).acquire(
        tenant_id="tenant-1",
        run_id="run-2",
        plan=plan,
        profile=SimpleNamespace(),
    )

    assert bundle.plan_id == "plan-2"
    assert calls == 2
