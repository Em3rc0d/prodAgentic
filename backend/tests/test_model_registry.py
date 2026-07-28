import pytest
import core.model_registry as model_registry

class MockModels:
    def list(self):
        class MockModel:
            def __init__(self, name):
                self.name = name
        return [MockModel("models/gemini-3.6-flash"), MockModel("gemini-3.5-flash-lite")]

class MockClient:
    def __init__(self):
        self.models = MockModels()

@pytest.mark.asyncio
async def test_validate_available_models_normalization():
    client = MockClient()
    await model_registry.validate_available_models(client)
    assert "gemini-3.6-flash" in model_registry._discoverable_models
    assert "gemini-3.5-flash-lite" in model_registry._discoverable_models
    assert "models/gemini-3.6-flash" not in model_registry._discoverable_models

def test_get_profile_readiness():
    model_registry._preflight_done = True
    model_registry._discoverable_models = {"gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"}
    assert model_registry.get_profile_readiness() == "READY"
    
    model_registry._discoverable_models = {"gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"}
    assert model_registry.get_profile_readiness() == "DEGRADED"
    
    model_registry._discoverable_models = set()
    assert model_registry.get_profile_readiness() == "NOT_READY"
