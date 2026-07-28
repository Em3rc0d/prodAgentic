import pytest
import os
from fastapi.testclient import TestClient
from main import app

@pytest.mark.integration
def test_full_pipeline():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not set")
    
    client = TestClient(app)
    response = client.get("/api/pipeline/stream?topic=Test&style=educational&idea=Testing")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
