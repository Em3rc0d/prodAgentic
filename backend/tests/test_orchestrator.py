import pytest
from agents.orchestrator import PipelineOrchestrator
from agents.router import RoutingExhausted
import asyncio

@pytest.mark.asyncio
async def test_orchestrator_stage_failed_exits_pipeline():
    class MockRouter:
        async def stream_generation(self, profile, sys, prompt, run_id):
            yield RoutingExhausted("Failed test")
            
    orch = PipelineOrchestrator(MockRouter())
    
    events = [evt async for evt in orch.run_pipeline_stream("idea", "topic", "style")]
    
    import json
    # Should emit stage.failed, and importantly, it should NOT proceed to the next stage (writer)
    assert any(json.loads(e["data"]).get("stage") == "stage.failed" for e in events)
    assert not any(json.loads(e["data"]).get("stage") == "writer" for e in events)
