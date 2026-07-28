import pytest
from fastapi.testclient import TestClient
from main import app
from core import model_registry

client = TestClient(app)

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

def test_health_ready_ready():
    model_registry._preflight_done = True
    model_registry._discoverable_models = {"gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"}
    
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "READY"}

def test_health_ready_degraded():
    model_registry._preflight_done = True
    model_registry._discoverable_models = {"gemini-3.1-flash-lite", "gemini-3.5-flash"} # Missing primary models
    
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "DEGRADED"

def test_health_ready_not_ready():
    model_registry._preflight_done = True
    model_registry._discoverable_models = set()
    
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "NOT_READY"
