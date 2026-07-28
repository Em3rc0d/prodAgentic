import pytest
import asyncio
from agents.orchestrator import run_pipeline_stream
from agents.router import StageFailedException
from agents.adapters.types import ModelExecutionError, ErrorCode

@pytest.mark.asyncio
async def test_attempt_reset_on_stage_failed():
    # We mock run_stage or agent_stream_func to raise StageFailedException
    
    async def mock_agent_stream(attempt_id):
        yield ("model_selected", "model-A")
        yield ("chunk", "part 1")
        # Fail mid-stream
        err = ModelExecutionError(ErrorCode.SERVICE_UNAVAILABLE, "midstream fail", True, True)
        raise StageFailedException(err)

    # In a real test, we would mock _research_agent.stream to use mock_agent_stream, 
    # but since run_pipeline_stream creates its own stages, we can test it by intercepting.
    pass # To be fully implemented in a detailed test
