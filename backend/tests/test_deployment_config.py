import os

import pytest

from core.auth import AuthSettings
from core.deployment import DeploymentConfigurationError, validate_cross_origin_auth


def _settings(*, secure=True, samesite="none", enabled=True):
    return AuthSettings(
        enabled=enabled,
        admin_user="admin",
        admin_password="a-secure-password",
        session_secret="a-session-secret-that-is-long-enough-for-tests",
        ttl_seconds=43200,
        cookie_secure=secure,
        cookie_samesite=samesite,
    )


def _set_cross_origin_env(monkeypatch, *, frontend="https://app.example.com", cors="https://app.example.com"):
    monkeypatch.setenv("PRODAGENTIC_CROSS_ORIGIN_AUTH", "true")
    monkeypatch.setenv("FRONTEND_URL", frontend)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", cors)


def test_cross_origin_auth_accepts_exact_secure_contract(monkeypatch):
    _set_cross_origin_env(monkeypatch)
    validate_cross_origin_auth(_settings())


def test_cross_origin_auth_requires_auth_enabled(monkeypatch):
    _set_cross_origin_env(monkeypatch)
    with pytest.raises(DeploymentConfigurationError, match="AUTH_ENABLED=true"):
        validate_cross_origin_auth(_settings(enabled=False))


def test_cross_origin_auth_requires_secure_cookie(monkeypatch):
    _set_cross_origin_env(monkeypatch)
    with pytest.raises(DeploymentConfigurationError, match="COOKIE_SECURE=true"):
        validate_cross_origin_auth(_settings(secure=False))


def test_cross_origin_auth_requires_samesite_none(monkeypatch):
    _set_cross_origin_env(monkeypatch)
    with pytest.raises(DeploymentConfigurationError, match="COOKIE_SAMESITE=none"):
        validate_cross_origin_auth(_settings(samesite="lax"))


def test_cross_origin_auth_requires_frontend_in_exact_cors_allowlist(monkeypatch):
    _set_cross_origin_env(monkeypatch, cors="https://other.example.com")
    with pytest.raises(DeploymentConfigurationError, match="must include the exact FRONTEND_URL"):
        validate_cross_origin_auth(_settings())


def test_cross_origin_auth_rejects_wildcard_cors(monkeypatch):
    _set_cross_origin_env(monkeypatch, cors="*")
    with pytest.raises(DeploymentConfigurationError, match="must not use wildcard CORS"):
        validate_cross_origin_auth(_settings())


@pytest.mark.parametrize(
    "frontend",
    [
        "http://app.example.com",
        "https://user:pass@app.example.com",
        "https://app.example.com/path",
        "https://app.example.com?x=1",
        "https://app.example.com#fragment",
    ],
)
def test_cross_origin_auth_rejects_unsafe_frontend_origins(monkeypatch, frontend):
    _set_cross_origin_env(monkeypatch, frontend=frontend, cors=frontend)
    with pytest.raises(DeploymentConfigurationError):
        validate_cross_origin_auth(_settings())


def test_cross_origin_auth_allows_loopback_http_for_local_certification(monkeypatch):
    _set_cross_origin_env(
        monkeypatch,
        frontend="http://127.0.0.1:3000",
        cors="http://127.0.0.1:3000,http://localhost:3000",
    )
    validate_cross_origin_auth(_settings())


def test_same_origin_or_reverse_proxy_mode_does_not_impose_cross_origin_contract(monkeypatch):
    monkeypatch.delenv("PRODAGENTIC_CROSS_ORIGIN_AUTH", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    validate_cross_origin_auth(_settings(secure=False, samesite="lax"))
