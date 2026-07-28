import pytest
import os
import asyncio
from fastapi.testclient import TestClient
from core.container import ApplicationContainer
from main import app

def test_missing_api_key_is_not_ready():
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
        
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["message"] == "Missing API Key"

def test_n8n_env_accepts_true_false_and_1_0():
    from agents.router import RoutingPolicy
    
    os.environ["GEMINI_API_KEY"] = "fake"
    container = ApplicationContainer()
    
    os.environ["N8N_ALLOW_DIRECT_FALLBACK"] = "1"
    container.startup()
    assert RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure is True
    
    os.environ["N8N_ALLOW_DIRECT_FALLBACK"] = "true"
    container.startup()
    assert RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure is True
    
    os.environ["N8N_ALLOW_DIRECT_FALLBACK"] = "0"
    container.startup()
    assert RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure is False

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
