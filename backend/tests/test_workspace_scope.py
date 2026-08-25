from types import SimpleNamespace

import pytest

import db.content_runs as content_runs_module
from core.context import LanguageCode
from core.settings import ApplicationSettings, LEGACY_WORKSPACE_ID
from db.content_runs import ContentRunRepository
from models.content_run import ContentRun


class FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append({"query": query, "update": update, "upsert": upsert})
        return SimpleNamespace(matched_count=1)


class FakeDb:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def _load_settings(monkeypatch, workspace_value=...):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "es")
    monkeypatch.delenv("APP_WORKSPACE_ID", raising=False)
    if workspace_value is not ...:
        monkeypatch.setenv("APP_WORKSPACE_ID", workspace_value)
    return ApplicationSettings.load()


def test_unset_workspace_uses_legacy_default(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.app_workspace_id == LEGACY_WORKSPACE_ID


def test_explicit_workspace_is_accepted(monkeypatch):
    settings = _load_settings(monkeypatch, "workspace_acme-01")
    assert settings.app_workspace_id == "workspace_acme-01"


@pytest.mark.parametrize("workspace", ["", "   ", "workspace/acme", "workspace acme", "@acme"])
def test_invalid_workspace_is_rejected(monkeypatch, workspace):
    with pytest.raises(ValueError):
        _load_settings(monkeypatch, workspace)


def test_legacy_content_run_deserializes_into_legacy_workspace():
    run = ContentRun(run_id="run-1", topic="AI", style="educational", idea="An idea")
    assert run.workspace_id == LEGACY_WORKSPACE_ID


@pytest.mark.asyncio
async def test_content_run_creation_persists_server_workspace(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    context = SimpleNamespace(
        run_id="run-1",
        workspace_id="workspace-a",
        topic="AI",
        style="educational",
        content_profile_id=None,
        content_profile_snapshot=None,
        requested_target_language=LanguageCode.ES,
        resolved_target_language=LanguageCode.ES,
        image_prompt_language=LanguageCode.EN,
    )

    created = await ContentRunRepository().create(context, "An idea")

    assert created is True
    inserted = collection.calls[-1]["update"]["$setOnInsert"]
    assert inserted["workspace_id"] == "workspace-a"
    assert collection.calls[-1]["query"] == {"run_id": "run-1"}
