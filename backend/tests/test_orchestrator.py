import json

import pytest

from agents.orchestrator import PipelineOrchestrator
from agents.router import RoutingExhausted


class DurableRunRepository:
    async def create(self, context, idea):
        return True

    async def mark_stage_started(self, *args, **kwargs):
        return None

    async def mark_attempt_failed(self, *args, **kwargs):
        return None

    async def mark_stage_completed(self, *args, **kwargs):
        return None

    async def mark_stage_failed(self, *args, **kwargs):
        return None

    async def mark_text_ready(self, *args, **kwargs):
        return None

    async def mark_ready_for_review(self, *args, **kwargs):
        return None

    async def mark_failed(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_orchestrator_stage_failed_exits_pipeline():
    class MockRouter:
        async def stream_generation(self, profile, sys, prompt, run_id):
            yield RoutingExhausted("Failed test")

    orch = PipelineOrchestrator(MockRouter())
    orch.content_runs = DurableRunRepository()

    events = [evt async for evt in orch.run_pipeline_stream("idea", "topic", "style")]

    # Should emit stage.failed, and importantly, it should NOT proceed to the next stage (writer)
    assert any(json.loads(e["data"]).get("stage") == "stage.failed" for e in events)
    assert not any(json.loads(e["data"]).get("stage") == "writer" for e in events)


@pytest.mark.asyncio
async def test_orchestrator_refuses_generation_without_authoritative_content_run():
    router_called = False

    class MockRouter:
        async def stream_generation(self, profile, sys, prompt, run_id):
            nonlocal router_called
            router_called = True
            yield RoutingExhausted("must never execute")

    class UnavailableRunRepository(DurableRunRepository):
        async def create(self, context, idea):
            return False

    orch = PipelineOrchestrator(MockRouter())
    orch.content_runs = UnavailableRunRepository()

    events = [evt async for evt in orch.run_pipeline_stream("idea", "topic", "style")]
    payloads = [json.loads(event["data"]) for event in events]

    assert payloads == [{
        "stage": "pipeline.persistence_failed",
        "reason": "Authoritative ContentRun could not be persisted",
        "run_id": payloads[0]["run_id"],
    }]
    assert router_called is False
