from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from agents.router import AttemptCompleted, AttemptFailed, AttemptStarted, ContentChunk, RoutingExhausted
from core.context import GenerationContext, LanguageCode
from domain.planning.models import BatchRequestConstraints, TargetWindow
from domain.profiles.models import (
    AgentPolicy,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    MigrationProvenance,
    NoveltyPolicy,
    ProfileIdentity,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest,
)
from infrastructure.planning.model_candidates import (
    CandidateGenerationError,
    RouterCandidateSource,
    _GEMINI_JSON_SCHEMA_KEYWORDS,
)


NOW = datetime(2026, 9, 17, 23, 35, tzinfo=timezone.utc)


def context() -> GenerationContext:
    return GenerationContext(
        run_id="planning-contract-test",
        topic="systems",
        style="creative-planning",
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.UNKNOWN,
        source_detection_confidence=0.0,
        requested_target_language=LanguageCode.ES,
        resolved_target_language=LanguageCode.ES,
        image_prompt_language=LanguageCode.ES,
        audience="builders",
        content_profile_id="profile-r41",
        content_profile_snapshot=None,
    )


def profile() -> ProfileVersion:
    payload = {
        "schema_version": 2,
        "profile_id": "profile-r41",
        "tenant_id": "tenant-r41",
        "version": 1,
        "identity": ProfileIdentity(name="Em3rc0d", account_type="education", summary="Technical education"),
        "goals": ("educate",),
        "audience": ("builders",),
        "editorial_strategy": EditorialStrategy(topic_families=("systems", "apis")),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(voice_traits=("direct",), target_language="es"),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(),
        "publishing_preferences": PublishingPreferences(channels=("manual_export",), default_batch_size=4),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW,
        "created_at": NOW,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    return provisional.model_copy(update={"digest": canonical_digest(provisional)})


def window() -> TargetWindow:
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


def idea(topic: str = "API contracts") -> dict:
    return {
        "role": "education",
        "topic": topic,
        "subtopics": ["validation"],
        "angle": "How explicit contracts prevent silent failures",
        "hook_pattern": "question",
        "target_effect": "understanding",
        "tentative_format": "carousel",
        "rationale": "Fits builders who need practical reliability patterns.",
        "claim_risk": "low",
    }


class SequenceRouter:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.requests = []

    async def stream_generation(self, request):
        self.requests.append(request)
        raw = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        attempt_id = f"attempt-{len(self.requests)}"
        yield AttemptStarted("test-model", attempt_id, "google")
        yield ContentChunk(raw, attempt_id)
        yield AttemptCompleted(attempt_id)


class FailureRouter:
    async def stream_generation(self, request):
        del request
        yield AttemptStarted("test-model", "attempt-1", "google")
        yield AttemptFailed("Model attempt failed: RATE_LIMITED", "attempt-1", "RATE_LIMITED")
        yield RoutingExhausted("Routing exhausted", "RATE_LIMITED")


@pytest.mark.asyncio
async def test_planning_requests_provider_enforced_structured_json():
    router = SequenceRouter([json.dumps({"ideas": [idea()]})])
    source = RouterCandidateSource(router)

    result = await source.generate(profile(), window(), BatchRequestConstraints(), 1)

    assert len(result) == 1
    request = router.requests[0]
    assert request.response_mime_type == "application/json"
    assert request.response_json_schema["type"] == "object"
    assert "ideas" in request.response_json_schema["properties"]
    ideas_schema = request.response_json_schema["properties"]["ideas"]
    assert ideas_schema["minItems"] == 1
    assert ideas_schema["maxItems"] == 1


def test_planning_provider_schema_uses_only_gemini_supported_keywords():
    router = SequenceRouter([json.dumps({"ideas": [idea(), idea("Second topic")]})])
    source = RouterCandidateSource(router)

    raw_schema = source.__class__.__module__  # prove import path stays stable for diagnostics
    assert raw_schema == "infrastructure.planning.model_candidates"

    from infrastructure.planning.model_candidates import _IdeaPool, _gemini_response_schema

    schema = _gemini_response_schema(_IdeaPool.model_json_schema(), target_pool_size=2)

    forbidden = {"minLength", "maxLength", "default", "pattern"}
    observed_schema_keywords = set()

    def walk(node, *, property_map=False):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if not property_map:
                observed_schema_keywords.add(key)
            if key in {"properties", "$defs"}:
                for child in value.values():
                    walk(child)
            else:
                walk(value)

    walk(schema)

    assert not (forbidden & observed_schema_keywords)
    assert observed_schema_keywords <= _GEMINI_JSON_SCHEMA_KEYWORDS
    assert schema["properties"]["ideas"]["minItems"] == 2
    assert schema["properties"]["ideas"]["maxItems"] == 2


@pytest.mark.asyncio
async def test_planning_preserves_router_failure_authority():
    source = RouterCandidateSource(FailureRouter())

    with pytest.raises(CandidateGenerationError) as caught:
        await source.generate(profile(), window(), BatchRequestConstraints(), 1)

    assert caught.value.code == "PLANNING_PROVIDER_RATE_LIMIT"


@pytest.mark.asyncio
async def test_invalid_json_is_bounded_and_classified():
    router = SequenceRouter(["not-json", "still-not-json"])
    source = RouterCandidateSource(router, max_contract_repairs=1)

    with pytest.raises(CandidateGenerationError) as caught:
        await source.generate(profile(), window(), BatchRequestConstraints(), 1)

    assert caught.value.code == "PLANNING_OUTPUT_JSON_INVALID"
    assert len(router.requests) == 2


@pytest.mark.asyncio
async def test_pool_size_mismatch_is_bounded_and_classified():
    router = SequenceRouter([
        json.dumps({"ideas": [idea()]}),
        json.dumps({"ideas": [idea()]}),
    ])
    source = RouterCandidateSource(router, max_contract_repairs=1)

    with pytest.raises(CandidateGenerationError) as caught:
        await source.generate(profile(), window(), BatchRequestConstraints(), 2)

    assert caught.value.code == "PLANNING_POOL_SIZE_MISMATCH"
    assert len(router.requests) == 2


@pytest.mark.asyncio
async def test_policy_filter_shortfall_gets_one_bounded_repair():
    router = SequenceRouter([
        json.dumps({"ideas": [idea("blocked-topic")]}),
        json.dumps({"ideas": [idea("blocked-topic")]}),
    ])
    source = RouterCandidateSource(router, max_contract_repairs=1)
    constraints = BatchRequestConstraints(avoid_topics=("blocked-topic",))

    with pytest.raises(CandidateGenerationError) as caught:
        await source.generate(profile(), window(), constraints, 1)

    assert caught.value.code == "PLANNING_POLICY_FILTER_SHORTFALL"
    assert len(router.requests) == 2
