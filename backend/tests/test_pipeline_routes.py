import pytest
from fastapi.testclient import TestClient
from main import app
from core.container import ApplicationContainer
from agents.idea_generator import GenerationIdeasFailed

client = TestClient(app)

def test_generation_ideas_failed_has_typed_http_response():
    container = ApplicationContainer()
    
    class MockPipelineService:
        async def generate_ideas(self, topic, style):
            raise GenerationIdeasFailed("Failed")
            
    container.pipeline_service = MockPipelineService()
    app.state.container = container
    
    response = client.post("/api/ideas", json={"topic": "AI", "style": "educational"})
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "IDEA_GENERATION_FAILED"
