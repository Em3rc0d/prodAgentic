import pytest
from fastapi.testclient import TestClient
from main import app
from core.container import ApplicationContainer
from agents.idea_generator import GenerationIdeasFailed

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
