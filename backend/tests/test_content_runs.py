import pytest

import db.content_runs as content_runs_module
from db.content_runs import ContentRunRepository
from models.content_run import ContentRunStatus, StageStatus


class FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append({"query": query, "update": update, "upsert": upsert})


class FakeDb:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


@pytest.mark.asyncio
async def test_visual_stage_failure_is_non_terminal(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    repo = ContentRunRepository()
    await repo.mark_stage_failed("run-1", "visual", "renderer unavailable", terminal=False)

    fields = collection.calls[-1]["update"]["$set"]
    assert fields["stages.visual.status"] == StageStatus.FAILED.value
    assert fields["stages.visual.last_error"] == "renderer unavailable"
    assert "status" not in fields
    assert "failure_stage" not in fields
    assert "failure_reason" not in fields


@pytest.mark.asyncio
async def test_text_stage_failure_is_terminal(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    repo = ContentRunRepository()
    await repo.mark_stage_failed("run-2", "edit", "routing exhausted", terminal=True)

    fields = collection.calls[-1]["update"]["$set"]
    assert fields["stages.edit.status"] == StageStatus.FAILED.value
    assert fields["status"] == ContentRunStatus.FAILED.value
    assert fields["failure_stage"] == "edit"
    assert fields["failure_reason"] == "routing exhausted"
