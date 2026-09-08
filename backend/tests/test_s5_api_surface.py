from __future__ import annotations

import main as main_module

from core.feature_flags import FeatureFlag, FeatureFlagRegistry


EXPECTED_S5_PATH_METHODS = {
    "/api/content-revisions/{revision_id}/render": "post",
    "/api/render-results/{render_id}": "get",
    "/api/render-assets/{asset_id}/content": "get",
    "/api/content-revisions/{revision_id}/render-preview": "get",
}


def test_s5_routes_are_mounted_on_the_canonical_fastapi_app():
    schema = main_module.app.openapi()
    paths = schema.get("paths", {})
    missing = []
    for path, method in EXPECTED_S5_PATH_METHODS.items():
        if path not in paths or method not in paths[path]:
            missing.append(f"{method.upper()} {path}")
    assert not missing, (
        f"missing S5 routes={missing}; main_file={main_module.__file__}; "
        f"mounted_paths={sorted(paths)}"
    )


def test_render_worker_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("MK1_ENABLED", raising=False)
    monkeypatch.delenv("MK1_RENDER_WORKER", raising=False)
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_RENDER_WORKER) is False


def test_render_worker_cannot_escape_master_gate(monkeypatch):
    monkeypatch.setenv("MK1_ENABLED", "false")
    monkeypatch.setenv("MK1_RENDER_WORKER", "true")
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_RENDER_WORKER) is False


def test_render_worker_can_be_explicitly_enabled_under_master_gate(monkeypatch):
    monkeypatch.setenv("MK1_ENABLED", "true")
    monkeypatch.setenv("MK1_RENDER_WORKER", "true")
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_RENDER_WORKER) is True
