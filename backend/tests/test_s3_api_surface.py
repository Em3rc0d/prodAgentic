from __future__ import annotations

from fastapi.routing import APIRoute

from core.feature_flags import FeatureFlag, FeatureFlagRegistry
from main import app


EXPECTED_S3_ROUTES = {
    ("POST", "/api/content-items/{content_id}/produce-text"),
    ("GET", "/api/generation-runs/{run_id}"),
    ("GET", "/api/content-revisions/{revision_id}"),
}


def test_s3_routes_are_mounted_on_the_canonical_fastapi_app():
    mounted = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            mounted.add((method, route.path))

    assert EXPECTED_S3_ROUTES <= mounted


def test_structured_agent_cell_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("MK1_ENABLED", raising=False)
    monkeypatch.delenv("MK1_STRUCTURED_AGENT_CELL", raising=False)
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_STRUCTURED_AGENT_CELL) is False


def test_structured_agent_cell_cannot_escape_master_gate(monkeypatch):
    monkeypatch.setenv("MK1_ENABLED", "false")
    monkeypatch.setenv("MK1_STRUCTURED_AGENT_CELL", "true")
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_STRUCTURED_AGENT_CELL) is False


def test_structured_agent_cell_can_be_explicitly_enabled_under_master_gate(monkeypatch):
    monkeypatch.setenv("MK1_ENABLED", "true")
    monkeypatch.setenv("MK1_STRUCTURED_AGENT_CELL", "true")
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_STRUCTURED_AGENT_CELL) is True
