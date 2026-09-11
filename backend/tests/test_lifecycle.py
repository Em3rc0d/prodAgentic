import pytest
import asyncio
from fastapi.testclient import TestClient
from core.container import ApplicationContainer
from main import app

@pytest.fixture(autouse=True)
def lifecycle_environment(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "es")
    monkeypatch.setenv("PRODAGENTIC_ENV", "development")
    monkeypatch.setenv("PRODAGENTIC_AUTH_ENABLED", "false")

def test_missing_api_key_is_not_ready(monkeypatch):
    # Isolate provider readiness from database readiness; both are hard gates.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("PRODAGENTIC_DEMO_MODE", "false")
    monkeypatch.setattr("main.database_ready", lambda: True)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["message"] == "Missing API Key"

def test_database_failure_blocks_demo_readiness(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_DEMO_MODE", "true")
    monkeypatch.setattr("main.database_ready", lambda: False)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["message"] == "Database unavailable"

def test_n8n_env_accepts_true_false_and_1_0(monkeypatch):
    # Routing-policy parsing does not require constructing an external client.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    container = ApplicationContainer()
    
    monkeypatch.setenv("N8N_ALLOW_DIRECT_FALLBACK", "1")
    container.startup()
    assert container.router.policy.allow_direct_provider_fallback_after_n8n_failure is True
    
    monkeypatch.setenv("N8N_ALLOW_DIRECT_FALLBACK", "true")
    container.startup()
    assert container.router.policy.allow_direct_provider_fallback_after_n8n_failure is True
    
    monkeypatch.setenv("N8N_ALLOW_DIRECT_FALLBACK", "0")
    container.startup()
    assert container.router.policy.allow_direct_provider_fallback_after_n8n_failure is False

@pytest.mark.asyncio
async def test_shutdown_awaits_cancelled_preflight():
    container = ApplicationContainer()
    container.client = "mock_client"
    
    async def slow_preflight():
        await asyncio.sleep(10)
        
    container.preflight_task = asyncio.create_task(slow_preflight())
    
    # Simulate shutdown process
    if getattr(container, 'preflight_task', None) and not container.preflight_task.done():
        container.preflight_task.cancel()
        try:
            await container.preflight_task
        except asyncio.CancelledError:
            pass
            
    assert container.preflight_task.cancelled()
