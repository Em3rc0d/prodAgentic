import asyncio

import pytest

from agents.adapters.types import ProviderAdapter
from agents.router import AttemptFailed, ModelExecutionRequest, ModelRouter, RoutingExhausted, RoutingPolicy
from core.context import GenerationContext, LanguageCode
from core.model_registry import ModelProfile
from core.validator import ArtifactType


class HangingAdapter(ProviderAdapter):
    async def stream(self, model: str, prompt: str, **kwargs):
        await asyncio.sleep(1)
        yield ("chunk", "this must never arrive")


@pytest.mark.asyncio
async def test_router_hard_deadline_cancels_hung_provider():
    context = GenerationContext(
        run_id="timeout-regression",
        topic="timeout",
        style="test",
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.EN,
        source_detection_confidence=1.0,
        requested_target_language=LanguageCode.EN,
        resolved_target_language=LanguageCode.EN,
        image_prompt_language=LanguageCode.EN,
    )
    policy = RoutingPolicy(
        max_transport_retries_per_route=1,
        max_language_repairs_per_stage=1,
        max_models_per_stage=2,
        max_total_attempts=5,
        max_stage_seconds=0.05,
    )
    router = ModelRouter(HangingAdapter(), None, routing_policy=policy)
    request = ModelExecutionRequest(
        context=context,
        model_profile=ModelProfile.QUALITY_TEXT,
        artifact_type=ArtifactType.IDEAS,
        system_instruction="system",
        user_prompt="prompt",
        expected_output_language=LanguageCode.EN,
    )

    started = asyncio.get_running_loop().time()
    events = [event async for event in router.stream_generation(request)]
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.5
    assert any(isinstance(event, AttemptFailed) and "deadline" in event.reason.lower() for event in events)
    assert isinstance(events[-1], RoutingExhausted)
    assert events[-1].reason == "Model stage deadline exceeded."
