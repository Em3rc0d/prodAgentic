from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core import model_registry


@pytest.mark.parametrize("catalog", [set(), {"gemini-3.5-flash-lite"}])
def test_advisory_discovery_never_erases_configured_routes(monkeypatch, catalog):
    cache = model_registry.PreflightCache()
    cache.is_valid = True
    cache.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    cache.discoverable_models = catalog
    monkeypatch.setattr(model_registry, "_cache", cache)
    models = model_registry.get_models_for_profile(model_registry.ModelProfile.QUALITY_TEXT)
    ids = [model.model_id for model in models]
    assert set(ids) == {"gemini-3.6-flash", "gemini-3.5-flash-lite"}
    if catalog:
        assert ids[0] == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("failed_refresh", [False, True])
def test_stale_or_failed_discovery_restores_configured_priority(monkeypatch, failed_refresh):
    cache = model_registry.PreflightCache()
    cache.is_valid = True
    cache.discoverable_models = {"gemini-3.5-flash-lite"}
    cache.expires_at = datetime.now(timezone.utc) + timedelta(hours=1 if failed_refresh else -1)
    cache.last_error_category = "MODEL_DISCOVERY_FAILED" if failed_refresh else None
    monkeypatch.setattr(model_registry, "_cache", cache)
    assert [model.model_id for model in model_registry.get_models_for_profile(
        model_registry.ModelProfile.QUALITY_TEXT
    )] == ["gemini-3.6-flash", "gemini-3.5-flash-lite"]


@pytest.mark.asyncio
async def test_failed_refresh_keeps_catalog_and_does_not_log_provider_details(caplog):
    cache = model_registry.PreflightCache()
    cache.is_valid = True
    cache.discoverable_models = {"gemini-3.5-flash-lite"}

    async def fail_list():
        raise RuntimeError("opaque-provider-detail")

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(list=fail_list)))
    await cache.refresh(client, force=True)
    assert cache.discoverable_models == {"gemini-3.5-flash-lite"}
    assert cache.last_error_category == "MODEL_DISCOVERY_FAILED"
    assert "opaque-provider-detail" not in caplog.text
