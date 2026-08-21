import copy

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import routes.content_runs as content_runs_routes
from models.content_run import ContentRunEditRequest, ContentRunStatus
from routes.content_runs import edit_content_run


class FakeCollection:
    def __init__(self, doc=None):
        self.doc = copy.deepcopy(doc)
        self.calls = []

    async def find_one(self, query):
        if self.doc is None:
            return None
        if "run_id" in query and self.doc.get("run_id") != query["run_id"]:
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update):
        self.calls.append({"query": query, "update": copy.deepcopy(update)})
        if self.doc is not None and "$set" in update:
            self.doc.update(copy.deepcopy(update["$set"]))


class FakeDb:
    def __init__(self, run_doc):
        self.collections = {
            "content_runs": FakeCollection(run_doc),
            "posts": FakeCollection({"run_id": run_doc["run_id"], "final_content": run_doc.get("final_content")}),
        }

    def __getitem__(self, name):
        return self.collections[name]


def visual_snapshot(prompt="old visual"):
    return {
        "render_id": "render-1",
        "status": "READY",
        "provider": "provider-a",
        "asset_url": "/assets/renders/render-1.png",
        "prompt_used": prompt,
        "requested_prompt": prompt,
        "aspect_ratio": "16:9",
        "style": "minimal",
        "idempotency_key": "key-12345678",
    }


@pytest.mark.asyncio
async def test_reviewable_run_can_edit_human_owned_outputs_without_rewriting_provenance(monkeypatch):
    original_stages = {
        "research": {
            "status": "COMPLETED",
            "output": "source material",
            "selected_model": "model-a",
            "provider": "provider-a",
        }
    }
    run_doc = {
        "run_id": "run-review",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": "old final",
        "visual_prompt": "old visual",
        "visual_render": visual_snapshot(),
        "stages": copy.deepcopy(original_stages),
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    updated = await edit_content_run(
        "run-review",
        ContentRunEditRequest(final_content="  new final  ", visual_prompt="new visual"),
    )

    assert updated["final_content"] == "new final"
    assert updated["visual_prompt"] == "new visual"
    assert updated["visual_render"] is None
    assert updated["status"] == ContentRunStatus.READY_FOR_REVIEW.value
    assert updated["stages"] == original_stages
    assert db["posts"].doc["final_content"] == "new final"


@pytest.mark.asyncio
async def test_final_copy_edit_keeps_current_visual_render(monkeypatch):
    snapshot = visual_snapshot()
    run_doc = {
        "run_id": "run-copy-only",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": "old final",
        "visual_prompt": "old visual",
        "visual_render": copy.deepcopy(snapshot),
        "stages": {},
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    updated = await edit_content_run(
        "run-copy-only",
        ContentRunEditRequest(final_content="new final"),
    )

    assert updated["visual_render"] == snapshot


@pytest.mark.asyncio
async def test_same_visual_prompt_does_not_invalidate_current_render(monkeypatch):
    snapshot = visual_snapshot()
    run_doc = {
        "run_id": "run-same-prompt",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": "final",
        "visual_prompt": "old visual",
        "visual_render": copy.deepcopy(snapshot),
        "stages": {},
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    updated = await edit_content_run(
        "run-same-prompt",
        ContentRunEditRequest(visual_prompt="old visual"),
    )

    assert updated["visual_render"] == snapshot


@pytest.mark.asyncio
async def test_approved_run_rejects_library_edits(monkeypatch):
    run_doc = {
        "run_id": "run-approved",
        "status": ContentRunStatus.APPROVED.value,
        "final_content": "approved copy",
        "visual_prompt": "approved visual",
        "visual_render": visual_snapshot("approved visual"),
        "stages": {},
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await edit_content_run(
            "run-approved",
            ContentRunEditRequest(final_content="mutated copy"),
        )

    assert exc.value.status_code == 409
    assert db["content_runs"].calls == []


def test_review_edit_rejects_blank_final_content():
    with pytest.raises(ValidationError):
        ContentRunEditRequest(final_content="   ")
