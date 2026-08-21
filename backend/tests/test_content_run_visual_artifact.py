from types import SimpleNamespace

import pytest

import db.content_runs as content_runs_module
from db.content_runs import ContentRunRepository
from models.content_run import ContentRunStatus
from models.visual import AspectRatio, RenderStatus, VisualRenderRequest, VisualRenderResponse, VisualStyle


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc):
        self.doc = dict(doc)
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append({"query": query, "update": update, "upsert": upsert})
        if self.doc.get("run_id") != query.get("run_id"):
            return UpdateResult(0)

        status_filter = query.get("status")
        if status_filter and self.doc.get("status") not in status_filter.get("$in", []):
            return UpdateResult(0)

        self.doc.update(update.get("$set", {}))
        return UpdateResult(1)


class FakeDb:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def render_request(run_id="run-1", prompt="diagram of an event-driven system"):
    return VisualRenderRequest(
        run_id=run_id,
        idempotency_key="intent-12345678",
        prompt=prompt,
        aspect_ratio=AspectRatio.WIDESCREEN,
        style=VisualStyle.MINIMAL,
    )


def render_response(prompt="diagram of an event-driven system"):
    return VisualRenderResponse(
        render_id="render-1",
        status=RenderStatus.READY,
        provider="MockImageProvider",
        asset_url="/assets/renders/render-1.png",
        width=1200,
        height=675,
        prompt_used=prompt,
    )


@pytest.mark.asyncio
async def test_reviewable_content_run_owns_successful_visual_render(monkeypatch):
    collection = FakeCollection({
        "run_id": "run-1",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "visual_prompt": "old prompt",
        "visual_render": None,
    })
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    attached = await ContentRunRepository().record_visual_render(
        render_request(),
        render_response(),
    )

    assert attached is True
    assert collection.doc["visual_prompt"] == "diagram of an event-driven system"
    snapshot = collection.doc["visual_render"]
    assert snapshot["render_id"] == "render-1"
    assert snapshot["status"] == RenderStatus.READY.value
    assert snapshot["asset_url"] == "/assets/renders/render-1.png"
    assert snapshot["aspect_ratio"] == "16:9"
    assert snapshot["style"] == "minimal"
    assert snapshot["idempotency_key"] == "intent-12345678"


@pytest.mark.asyncio
async def test_approved_content_run_cannot_have_visual_render_overwritten(monkeypatch):
    original = {"render_id": "approved-render", "status": "READY"}
    collection = FakeCollection({
        "run_id": "run-1",
        "status": ContentRunStatus.APPROVED.value,
        "visual_prompt": "approved prompt",
        "visual_render": original,
    })
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    attached = await ContentRunRepository().record_visual_render(
        render_request(prompt="mutated prompt"),
        render_response(prompt="mutated prompt"),
    )

    assert attached is False
    assert collection.doc["visual_prompt"] == "approved prompt"
    assert collection.doc["visual_render"] == original


@pytest.mark.asyncio
async def test_unknown_run_id_does_not_create_or_attach_visual_artifact(monkeypatch):
    collection = FakeCollection({
        "run_id": "known-run",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
    })
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    attached = await ContentRunRepository().record_visual_render(
        render_request(run_id="fallback-run"),
        render_response(),
    )

    assert attached is False
    assert "visual_render" not in collection.doc
