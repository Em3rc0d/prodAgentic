import asyncio

import pytest
from fastapi.testclient import TestClient

from agents.adapters.image import ImageRenderProvider, ImageRenderResult
from core.visual import VisualRenderService
from db.content_runs import ContentRunRepository
from main import app


class MockPollinationsProvider(ImageRenderProvider):
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        if prompt == "trigger_error":
            raise Exception("Provider error")
        prompt_used = f"{prompt} {style}".strip() if style else prompt
        return ImageRenderResult(
            url="http://mock-url.com/image.png",
            prompt_used=prompt_used,
            aspect_ratio=aspect_ratio,
            width=1280,
            height=720,
        )


@pytest.fixture
def client():
    with TestClient(app) as client:
        mock_provider = MockPollinationsProvider()
        mock_service = VisualRenderService(mock_provider, storage_dir="scratch/tests_static")

        async def mock_fetch_image(url: str) -> bytes:
            if "timeout" in url:
                raise asyncio.TimeoutError("Timeout!")
            return b"\x89PNG\r\n\x1a\nmock_image_bytes"

        mock_service._fetch_image = mock_fetch_image
        app.state.container.visual_service = mock_service
        yield client


def test_visual_render_success(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-unique-1",
        "prompt": "cyberpunk city",
        "aspect_ratio": "16:9",
        "style": "cinematic",
    }
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["asset_url"].startswith("/assets/renders/")
    assert data["prompt_used"] == "cyberpunk city cinematic"


def test_visual_render_idempotency(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-unique-2",
        "prompt": "first prompt",
    }
    res1 = client.post("/api/visual-renders", json=req).json()

    req["prompt"] = "second prompt"
    res2 = client.post("/api/visual-renders", json=req).json()

    assert res1["render_id"] == res2["render_id"]
    assert res1["prompt_used"] == res2["prompt_used"]
    assert res1["prompt_used"] == "first prompt"


def test_visual_render_validation_error(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-unique-3",
        "prompt": "city",
        "aspect_ratio": "INVALID",
    }
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 422


def test_visual_render_provider_error(client):
    req = {
        "run_id": "test-run",
        "idempotency_key": "key-unique-4",
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
        "idempotency_key": "key-unique-5",
        "prompt": "timeout",
    }

    original_provider = app.state.container.visual_service.provider

    class TimeoutProvider(ImageRenderProvider):
        async def render(self, prompt, aspect_ratio="16:9", style=""):
            return ImageRenderResult(
                url="http://mock-url.com/timeout.png",
                prompt_used=prompt,
                aspect_ratio=aspect_ratio,
                width=1280,
                height=720,
            )

    app.state.container.visual_service.provider = TimeoutProvider()
    response = client.post("/api/visual-renders", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    app.state.container.visual_service.provider = original_provider


def test_visual_render_calls_content_run_attachment(client, monkeypatch):
    attached = {}

    async def capture_attachment(self, req, result):
        attached["run_id"] = req.run_id
        attached["render_id"] = result.render_id
        attached["status"] = result.status.value
        return True

    monkeypatch.setattr(ContentRunRepository, "record_visual_render", capture_attachment)

    response = client.post("/api/visual-renders", json={
        "run_id": "owned-run",
        "idempotency_key": "key-owned-123",
        "prompt": "owned visual",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert attached["run_id"] == "owned-run"
    assert attached["render_id"] == response.json()["render_id"]
    assert attached["status"] == "READY"


def test_visual_render_persistence_failure_does_not_fabricate_render_failure(client, monkeypatch):
    async def fail_attachment(self, req, result):
        raise RuntimeError("mongo unavailable")

    monkeypatch.setattr(ContentRunRepository, "record_visual_render", fail_attachment)

    response = client.post("/api/visual-renders", json={
        "run_id": "owned-run",
        "idempotency_key": "key-owned-456",
        "prompt": "still render this",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["asset_url"].startswith("/assets/renders/")
