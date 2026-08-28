import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import routes.pipeline as pipeline_routes
from main import app
from core.container import ApplicationContainer
from core.context import ImagePromptLanguageCode, TargetLanguageCode
from agents.idea_generator import GenerationIdeasFailed
from models.grounding import SourcePacket

client = TestClient(app)


def test_generation_ideas_failed_has_typed_http_response():
    container = ApplicationContainer()

    class MockRouter:
        def _get_adapters(self):
            return [("test", None)]

    class MockPipelineService:
        async def generate_ideas(self, topic, style, target_language="es"):
            raise GenerationIdeasFailed("Failed")

    container.router = MockRouter()
    container.pipeline_service = MockPipelineService()
    app.state.container = container

    response = client.post("/api/ideas", json={"topic": "AI", "style": "educational"})
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "IDEA_GENERATION_FAILED"


def test_ideas_returns_503_when_no_provider_is_viable():
    container = ApplicationContainer()

    class MockRouter:
        def _get_adapters(self):
            return []

    class MockPipelineService:
        pass

    container.router = MockRouter()
    container.pipeline_service = MockPipelineService()
    app.state.container = container

    response = client.post("/api/ideas", json={"topic": "AI", "style": "educational"})
    assert response.status_code == 503
    assert response.json()["detail"] == "No viable provider adapters available."


def test_stream_returns_503_when_no_provider_is_viable():
    container = ApplicationContainer()

    class MockRouter:
        def _get_adapters(self):
            return []

    class MockPipelineService:
        pass

    container.router = MockRouter()
    container.pipeline_service = MockPipelineService()
    app.state.container = container

    response = client.get("/api/pipeline/stream?idea=test&topic=test")
    assert response.status_code == 503
    assert response.json()["detail"] == "No viable provider adapters available."


def test_stream_returns_503_when_mongo_is_unavailable():
    container = ApplicationContainer()

    class MockRouter:
        def _get_adapters(self):
            return [("test", None)]

    class MockPipelineService:
        pass

    container.router = MockRouter()
    container.pipeline_service = MockPipelineService()
    app.state.container = container

    response = client.get("/api/pipeline/stream?idea=test&topic=test")
    assert response.status_code == 503
    assert response.json()["detail"] == "MongoDB required for durable content generation"


def request_for_workspace(workspace_id: str):
    settings = SimpleNamespace(app_workspace_id=workspace_id)
    container = SimpleNamespace(settings=settings)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


@pytest.mark.asyncio
async def test_stream_resolves_source_packet_in_server_workspace_before_orchestration(monkeypatch):
    packet = SourcePacket(
        packet_id="packet-1",
        workspace_id="server-workspace",
        title="Generation packet",
    )
    repository_calls = []
    pipeline_calls = []

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            repository_calls.append((workspace_id, packet_id))
            return packet

    class FakePipeline:
        async def run_pipeline_stream(self, *args, **kwargs):
            pipeline_calls.append((args, kwargs))
            yield {"data": json.dumps({"stage": "complete", "run_id": "run-1"})}

    async def no_profile(_profile_id):
        return None, None

    monkeypatch.setattr(pipeline_routes, "get_db", lambda: object())
    monkeypatch.setattr(pipeline_routes, "SourcePacketRepository", FakeRepository)
    monkeypatch.setattr(pipeline_routes, "_resolve_content_profile", no_profile)

    response = await pipeline_routes.pipeline_stream(
        request=request_for_workspace("server-workspace"),
        idea="idea",
        topic="topic",
        style="educational",
        target_language=TargetLanguageCode.ES,
        image_prompt_language=ImagePromptLanguageCode.EN,
        content_profile_id=None,
        source_packet_id="packet-1",
        pipeline=FakePipeline(),
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert repository_calls == [("server-workspace", "packet-1")]
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0][1]["source_packet"] is packet
    assert any('"stage": "complete"' in (chunk.decode() if isinstance(chunk, bytes) else chunk) for chunk in chunks)


@pytest.mark.asyncio
async def test_stream_unknown_or_cross_workspace_packet_is_404_before_orchestration(monkeypatch):
    pipeline_called = False

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            assert workspace_id == "server-workspace"
            assert packet_id == "hidden-packet"
            return None

    class FakePipeline:
        async def run_pipeline_stream(self, *args, **kwargs):
            nonlocal pipeline_called
            pipeline_called = True
            if False:
                yield None

    monkeypatch.setattr(pipeline_routes, "get_db", lambda: object())
    monkeypatch.setattr(pipeline_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await pipeline_routes.pipeline_stream(
            request=request_for_workspace("server-workspace"),
            idea="idea",
            topic="topic",
            style="educational",
            target_language=TargetLanguageCode.ES,
            image_prompt_language=ImagePromptLanguageCode.EN,
            content_profile_id=None,
            source_packet_id="hidden-packet",
            pipeline=FakePipeline(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Source packet not found"
    assert pipeline_called is False
