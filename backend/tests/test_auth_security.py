import time

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from core.auth import AuthConfigurationError, AuthSettings, SessionManager, SessionValidationError, router, security_boundary


def settings(**changes):
    values = {"enabled": True, "admin_user": "admin", "admin_password": "correct-horse-battery", "session_secret": "s" * 32, "ttl_seconds": 3600, "cookie_secure": True, "cookie_samesite": "lax"}
    values.update(changes)
    return AuthSettings(**values)


def test_session_round_trip_and_csrf_binding():
    manager = SessionManager(settings())
    token, issued = manager.issue()
    verified = manager.verify(token)
    assert verified["sub"] == "admin"
    assert verified["csrf"] == issued["csrf"]
    assert len(verified["sid"]) >= 20


def test_tampered_session_is_rejected():
    manager = SessionManager(settings())
    token, _ = manager.issue()
    body, signature = token.split(".", 1)
    with pytest.raises(SessionValidationError, match="signature"):
        manager.verify(f"{body}x.{signature}")


def test_expired_session_is_rejected(monkeypatch):
    manager = SessionManager(settings(ttl_seconds=300))
    token, issued = manager.issue()
    monkeypatch.setattr(time, "time", lambda: issued["exp"] + 1)
    with pytest.raises(SessionValidationError, match="expired"):
        manager.verify(token)


def test_credentials_require_both_values():
    manager = SessionManager(settings())
    assert manager.credentials_match("admin", "correct-horse-battery")
    assert not manager.credentials_match("admin", "wrong")
    assert not manager.credentials_match("other", "correct-horse-battery")


def test_enabled_auth_fails_closed_on_weak_secrets(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_AUTH_ENABLED", "true")
    monkeypatch.setenv("PRODAGENTIC_ADMIN_PASSWORD", "short")
    monkeypatch.setenv("PRODAGENTIC_SESSION_SECRET", "short")
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env()


@pytest.fixture
def http_client():
    app = FastAPI()
    auth_settings = settings(cookie_secure=False)
    app.state.auth_settings = auth_settings
    app.state.session_manager = SessionManager(auth_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(security_boundary)
    app.include_router(router, prefix="/api")

    @app.get("/api/protected")
    async def protected_read():
        return {"ok": True}

    @app.post("/api/protected")
    async def protected_write():
        return {"ok": True}

    with TestClient(app) as client:
        yield client


def test_http_boundary_rejects_unauthenticated_access(http_client):
    response = http_client.get("/api/protected")
    assert response.status_code == 401
    assert response.headers["x-frame-options"] == "DENY"


def test_http_boundary_allows_unauthenticated_cors_preflight_only(http_client):
    preflight = http_client.options(
        "/api/protected",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"

    # Permitting negotiation must not weaken the actual protected operation.
    assert http_client.post("/api/protected").status_code == 401


def test_http_boundary_rejects_missing_csrf_and_accepts_bound_token(http_client):
    login_response = http_client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-battery"})
    assert login_response.status_code == 200
    assert "HttpOnly" in login_response.headers["set-cookie"]
    csrf_token = login_response.json()["csrf_token"]

    assert http_client.get("/api/protected").status_code == 200
    assert http_client.post("/api/protected").status_code == 403
    assert http_client.post("/api/protected", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert http_client.post("/api/protected", headers={"X-CSRF-Token": csrf_token}).status_code == 200
