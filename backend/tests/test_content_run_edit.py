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


def grounding_snapshot():
    return {
        "assessment_id": "assessment-1",
        "packet_id": "packet-1",
        "content_sha256": "a" * 64,
        "evaluator_version": "test-v1",
        "extraction_complete": True,
        "claims": [],
    }


def grounding_gate():
    return {
        "policy_version": "grounding-policy-v1",
        "decision": "PASS",
        "blocking_claim_ids": [],
        "warning_claim_ids": [],
        "reasons": [],
    }


def grounding_review():
    return {
        "review_id": "review-1",
        "decision": "VERIFIED",
        "source": "explicit_user_action",
        "content_sha256": "a" * 64,
        "assessment_sha256": "b" * 64,
        "policy_version": "grounding-policy-v1",
        "warning_claim_ids": [],
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
        "grounding_assessment": grounding_snapshot(),
        "grounding_gate": grounding_gate(),
        "grounding_review": grounding_review(),
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
    assert updated["grounding_assessment"] is None
    assert updated["grounding_gate"] is None
    assert updated["grounding_review"] is None
    assert updated["status"] == ContentRunStatus.READY_FOR_REVIEW.value
    assert updated["stages"] == original_stages
    assert db["posts"].doc["final_content"] == "new final"


@pytest.mark.asyncio
async def test_final_copy_edit_keeps_current_visual_render_but_invalidates_grounding(monkeypatch):
    snapshot = visual_snapshot()
    run_doc = {
        "run_id": "run-copy-only",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": "old final",
        "visual_prompt": "old visual",
        "visual_render": copy.deepcopy(snapshot),
        "grounding_assessment": grounding_snapshot(),
        "grounding_gate": grounding_gate(),
        "grounding_review": grounding_review(),
        "stages": {},
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    updated = await edit_content_run(
        "run-copy-only",
        ContentRunEditRequest(final_content="new final"),
    )

    assert updated["visual_render"] == snapshot
    assert updated["grounding_assessment"] is None
    assert updated["grounding_gate"] is None
    assert updated["grounding_review"] is None


@pytest.mark.asyncio
async def test_same_final_copy_preserves_grounding(monkeypatch):
    assessment = grounding_snapshot()
    gate = grounding_gate()
    review = grounding_review()
    run_doc = {
        "run_id": "run-same-copy",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": "same final",
        "visual_prompt": "old visual",
        "visual_render": visual_snapshot(),
        "grounding_assessment": copy.deepcopy(assessment),
        "grounding_gate": copy.deepcopy(gate),
        "grounding_review": copy.deepcopy(review),
        "stages": {},
    }
    db = FakeDb(run_doc)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    updated = await edit_content_run(
        "run-same-copy",
        ContentRunEditRequest(final_content="  same final  "),
    )

    assert updated["grounding_assessment"] == assessment
    assert updated["grounding_gate"] == gate
    assert updated["grounding_review"] == review


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
