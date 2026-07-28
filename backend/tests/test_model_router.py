import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from core.model_registry import ModelProfile, REGISTRY, ModelDefinition
from agents.router import ModelRouter
from agents.adapters.types import ProviderAdapter, ModelExecutionResult, ModelExecutionError, ErrorCode

class MockAdapter(ProviderAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        if self.call_count >= len(self.responses):
            raise Exception("Mock exhausted")
        resp = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp
        
    async def stream(self, model: str, prompt: str, **kwargs):
        pass

@pytest.mark.asyncio
async def test_router_circuit_breaker():
    err = ModelExecutionError(ErrorCode.MODEL_NOT_FOUND, "not found", False, True)
    success = ModelExecutionResult(actual_model="gemini-3.1-flash-lite", content="hello")
    # google_adapter is evaluated LAST in _get_adapters()
    # Wait, _get_adapters() returns [n8n, google].
    # So if we want to test circuit breaker, n8n (adapter1) fails, google (adapter2) succeeds.
    adapter1 = MockAdapter([err])
    adapter2 = MockAdapter([success])
    
    # We want n8n to fail first, then google succeeds
    router = ModelRouter(n8n_adapter=adapter1, google_adapter=adapter2)
    
    with patch("agents.router.get_models_for_profile", return_value=[ModelDefinition(model_id="gemini-3.5-flash-lite"), ModelDefinition(model_id="gemini-3.1-flash-lite")]):
        actual, content = await router.generate(ModelProfile.ECONOMY_TEXT, "sys", "prompt", "123")
    
        assert content == "hello"
        assert actual == "gemini-3.1-flash-lite"
        # adapter1 fails with MODEL_NOT_FOUND, so gemini-3.5-flash-lite gets broken
        assert "gemini-3.5-flash-lite" in router._circuit_broken_models

@pytest.mark.asyncio
async def test_router_retry_budget():
    err = ModelExecutionError(ErrorCode.RATE_LIMITED, "rate limited", True, False)
    success = ModelExecutionResult(actual_model="modelA", content="hello")
    adapter1 = MockAdapter([err, success])
    adapter2 = MockAdapter([err, err])
    router = ModelRouter(google_adapter=adapter1, n8n_adapter=adapter2)
    
    with patch("agents.router.get_models_for_profile", return_value=[ModelDefinition(model_id="modelA")]):
        with patch("asyncio.sleep", new_callable=AsyncMock): # Skip sleeps
            # Wait, if we use MockAdapter for both, the loop over _get_adapters() will call google_adapter first,
            # which fails with RATE_LIMITED. It's the first adapter (index 0).
            # The second adapter (n8n_adapter) is ALSO MockAdapter.
            # So the loop continues to n8n_adapter, which returns success!
            # Let's adjust MockAdapter to return success on the second call.
            actual, content = await router.generate(ModelProfile.ECONOMY_TEXT, "sys", "prompt", "123")
            assert content == "hello"
            assert adapter1.call_count == 2
