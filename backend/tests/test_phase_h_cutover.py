from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

import core.cutover as cutover_module
from core.cutover import (
    CUTOVER_ERROR_CODE,
    cutover_readiness,
    is_legacy_write_authority,
    production_cutover_boundary,
)
from core.feature_flags import FeatureFlag, FeatureFlagRegistry
from core.production import ProductionConfigurationError, validate_production_environment


def _all_mk1(monkeypatch, *, cutover: bool = True):
    for flag in FeatureFlag:
        monkeypatch.setenv(flag.value, "true")
    monkeypatch.setenv(FeatureFlag.MK1_PRODUCTION_CUTOVER.value, "true" if cutover else "false")


def _request(*, method: str, path: str, registry, container=None) -> Request:
    app = SimpleNamespace(
        state=SimpleNamespace(
            feature_flags=registry,
            container=container,
        )
    )
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "app": app,
        }
    )


def test_cutover_flag_requires_every_certified_v1_authority(monkeypatch):
    _all_mk1(monkeypatch)
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_PRODUCTION_CUTOVER)
    assert all(registry.enabled(flag) for flag in FeatureFlag)

    monkeypatch.setenv(FeatureFlag.MK1_ANALYTICS_WORKER.value, "false")
    with pytest.raises(ValueError, match="MK1_ANALYTICS_WORKER"):
        FeatureFlagRegistry.from_env()


def test_cutover_is_explicit_and_default_off(monkeypatch):
    for flag in FeatureFlag:
        monkeypatch.delenv(flag.value, raising=False)
    registry = FeatureFlagRegistry.from_env()
    assert not registry.enabled(FeatureFlag.MK1_PRODUCTION_CUTOVER)
    assert not registry.enabled(FeatureFlag.MK1_ENABLED)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/ideas"),
        ("GET", "/api/pipeline/stream"),
        ("POST", "/api/visual-renders"),
        ("PATCH", "/api/content-runs/run-1"),
        ("POST", "/api/content-runs/run-1/approve"),
        ("POST", "/api/content-runs/run-1/publish"),
        ("POST", "/api/content-runs/run-1/schedule"),
        ("DELETE", "/api/content-runs/run-1/schedule"),
        ("POST", "/api/content-profiles"),
        ("PATCH", "/api/content-profiles/profile-1"),
        ("POST", "/api/content-profiles/profile-1/default"),
        ("DELETE", "/api/content-profiles/profile-1"),
        ("PATCH", "/api/posts/507f1f77bcf86cd799439011/status"),
        ("DELETE", "/api/posts/507f1f77bcf86cd799439011"),
    ],
)
def test_legacy_mutation_authorities_are_exhaustively_matched(method, path):
    assert is_legacy_write_authority(method, path)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/posts"),
        ("GET", "/api/content-runs"),
        ("GET", "/api/content-runs/run-1"),
        ("GET", "/api/content-profiles"),
        ("GET", "/api/content-profiles/profile-1"),
        ("POST", "/api/profiles/profile-1/batches"),
        ("POST", "/api/analytics/performance-summary/rebuild"),
    ],
)
def test_historical_reads_and_mk1_writes_are_not_misclassified(method, path):
    assert not is_legacy_write_authority(method, path)


@pytest.mark.asyncio
async def test_active_cutover_rejects_side_effectful_legacy_get_before_route_logic(monkeypatch):
    _all_mk1(monkeypatch)
    registry = FeatureFlagRegistry.from_env()
    request = _request(method="GET", path="/api/pipeline/stream", registry=registry)
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return JSONResponse({"unexpected": True})

    response = await production_cutover_boundary(request, call_next)
    assert response.status_code == 410
    assert not called
    payload = json.loads(response.body)
    assert payload["code"] == CUTOVER_ERROR_CODE
    assert payload["replacement_authority"] == "BatchPlanner + Structured Agent Cell"


@pytest.mark.asyncio
async def test_rollback_switch_restores_legacy_code_path_without_schema_change(monkeypatch):
    _all_mk1(monkeypatch, cutover=False)
    registry = FeatureFlagRegistry.from_env()
    request = _request(method="POST", path="/api/ideas", registry=registry)

    async def call_next(_request):
        return JSONResponse({"legacy_path_reachable": True}, status_code=204)

    response = await production_cutover_boundary(request, call_next)
    assert response.status_code == 204


class _RunningTask:
    def done(self):
        return False


def test_cutover_readiness_is_non_secret_and_requires_worker_authority(monkeypatch):
    _all_mk1(monkeypatch)
    registry = FeatureFlagRegistry.from_env()
    container = SimpleNamespace(
        scheduler_task=None,
        s10_publish_task=_RunningTask(),
        s11_analytics_task=_RunningTask(),
    )
    request = _request(method="GET", path="/health/cutover", registry=registry, container=container)
    monkeypatch.setattr(cutover_module, "database_ready", lambda: True)

    payload, status = cutover_readiness(request)
    assert status == 200
    assert payload["status"] == "READY"
    assert payload["mk0_write_authority"] == "DISABLED"
    assert payload["mk0_scheduler"] == "DISABLED"
    assert payload["mk1_publish_worker"] == "RUNNING"
    assert payload["mk1_analytics_worker"] == "RUNNING"
    serialized = json.dumps(payload).lower()
    for forbidden in ("access_token", "client_secret", "session_secret", "external_post_id"):
        assert forbidden not in serialized


def test_cutover_readiness_fails_closed_when_worker_is_not_running(monkeypatch):
    _all_mk1(monkeypatch)
    registry = FeatureFlagRegistry.from_env()
    container = SimpleNamespace(
        scheduler_task=None,
        s10_publish_task=None,
        s11_analytics_task=_RunningTask(),
    )
    request = _request(method="GET", path="/health/cutover", registry=registry, container=container)
    monkeypatch.setattr(cutover_module, "database_ready", lambda: True)
    payload, status = cutover_readiness(request)
    assert status == 503
    assert payload["status"] == "NOT_READY"


def _production_env(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_ENV", "production")
    monkeypatch.setenv("PRODAGENTIC_AUTH_ENABLED", "true")
    monkeypatch.setenv("PRODAGENTIC_COOKIE_SECURE", "true")
    monkeypatch.setenv("PRODAGENTIC_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("FRONTEND_URL", "https://app.prodagentic.example")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.prodagentic.example")
    monkeypatch.setenv("PRODAGENTIC_ASSET_ROOT", "/tmp/prodagentic-assets")
    monkeypatch.setenv("LINKEDIN_STATIC_FALLBACK_ENABLED", "false")


def test_production_configuration_contract_accepts_safe_cutover_runtime(monkeypatch):
    _production_env(monkeypatch)
    validate_production_environment()


def test_production_configuration_rejects_wildcard_cors(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(ProductionConfigurationError, match="wildcards"):
        validate_production_environment()
