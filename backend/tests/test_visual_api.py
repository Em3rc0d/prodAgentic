import pytest
from fastapi.testclient import TestClient
from main import app
from core.visual import VisualRenderService
from agents.adapters.image import ImageRenderResult, ImageRenderProvider
from models.visual import RenderStatus
import asyncio
import uuid

class MockPollinationsProvider(ImageRenderProvider):
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        if prompt == "trigger_error":
            raise Exception("Provider error")
        return ImageRenderResult(
            url="http://mock-url.com/image.png",
            prompt_used=prompt,
            aspect_ratio=aspect_ratio
        )

# Mock httpx response
class MockResponse:
    def __init__(self, content=b"mock_image_bytes", status_code=200):
        self.content = content
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception("HTTP Error")

@pytest.fixture
def client():
    with TestClient(app) as client:
        # Inject mock service
        mock_provider = MockPollinationsProvider()
        mock_service = VisualRenderService(mock_provider, storage_dir="scratch/tests_static")
        
        # Patch the _fetch_with_retries to avoid real network call
        async def mock_fetch(*args, **kwargs):
            if "timeout" in args[1]:
                raise asyncio.TimeoutError("Timeout!")
            return MockResponse()
            
        mock_service._fetch_with_retries = mock_fetch
        app.state.container.visual_service = mock_service
        yield client

def test_visual_render_success(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-1",
        "prompt": "cyberpunk city",
        "aspect_ratio": "16:9",
        "style": "cyberpunk"
    }
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["asset_url"].startswith("/assets/renders/")
    assert data["prompt_used"] == "cyberpunk city"

def test_visual_render_idempotency(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-2",
        "prompt": "first prompt",
    }
    res1 = client.post("/api/visual-renders", json=req).json()
    
    # Change prompt but keep key
    req["prompt"] = "second prompt"
    res2 = client.post("/api/visual-renders", json=req).json()
    
    assert res1["render_id"] == res2["render_id"]
    assert res1["prompt_used"] == res2["prompt_used"]
    assert res1["prompt_used"] == "first prompt"

def test_visual_render_validation_error(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-3",
        "prompt": "city",
        "aspect_ratio": "INVALID"
    }
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 422 # FastAPI validation

def test_visual_render_provider_error(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-4",
        "prompt": "trigger_error",
    }
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert "error" in data["error_message"].lower() or "failed" in data["error_message"].lower()

def test_visual_render_timeout(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-5",
        "prompt": "timeout", # Will be caught by our mock_fetch if url has 'timeout'
    }
    
    # Modify mock provider to return a URL with 'timeout' in it
    original_provider = app.state.container.visual_service.provider
    class TimeoutProvider(ImageRenderProvider):
        async def render(self, prompt, aspect_ratio="16:9", style=""):
            return ImageRenderResult(url="http://mock-url.com/timeout.png", prompt_used=prompt, aspect_ratio=aspect_ratio)
            
    app.state.container.visual_service.provider = TimeoutProvider()
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    
    # Restore
    app.state.container.visual_service.provider = original_provider
