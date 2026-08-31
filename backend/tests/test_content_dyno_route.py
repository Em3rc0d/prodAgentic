from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import routes.content_dyno as dyno_routes
from models.content_dyno import (
    EditorialVerdict,
    HumanEditorialReview,
    HumanEditorialReviewInput,
)
from models.content_run import ContentRun, ContentRunStatus, VisualArtifactSnapshot


VISUAL_SHA = "a" * 64


class FakeCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query):
        if query.get("run_id") != self.doc.get("run_id"):
            return None
        return self.doc

    async def update_one(self, query, update):
        if query.get("updated_at") != self.doc.get("updated_at"):
            return SimpleNamespace(matched_count=0)
        self.doc.update(update["$set"])
        return SimpleNamespace(matched_count=1)


class FakeDB:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def review_input() -> HumanEditorialReviewInput:
    return HumanEditorialReviewInput(
        topic_fidelity=0.91,
        pov_strength=0.88,
        human_voice=0.89,
        usefulness=0.92,
        visual_message_fit=0.90,
        publish_readiness=0.87,
        verdict=EditorialVerdict.WOULD_PUBLISH_NOW,
        notes=["Would publish as reviewed."],
    )


def reviewable_run() -> ContentRun:
    visual = VisualArtifactSnapshot(
        render_id="render-1",
        status="READY",
        provider="DeterministicBrowserRenderer",
        asset_url="/assets/renders/render-1.png",
        asset_sha256=VISUAL_SHA,
        width=1080,
        height=1350,
        prompt_used="technical editorial",
        requested_prompt="technical editorial",
        aspect_ratio="4:5",
        style="technical_editorial",
        idempotency_key="dyno-route-render",
    )
    return ContentRun(
        run_id="run-1",
        workspace_id="workspace-1",
        status=ContentRunStatus.READY_FOR_REVIEW,
        topic="Exact dyno review binding",
        style="educational",
        idea="Bind judgement to the reviewed asset.",
        final_content="This exact text is the reviewed editorial asset.",
        visual_prompt="technical editorial",
        visual_render=visual,
    )


@pytest.mark.asyncio
async def test_submit_dyno_review_binds_server_owned_run_content_and_visual(monkeypatch):
    run = reviewable_run()
    fake_db = FakeDB(run.model_dump(mode="python"))
    monkeypatch.setattr(dyno_routes, "get_db", lambda: fake_db)

    result = await dyno_routes.submit_content_dyno_review(run.run_id, review_input())

    expected_content_sha = hashlib.sha256(run.final_content.encode("utf-8")).hexdigest()
    assert result["run_id"] == run.run_id
    assert result["final_content_sha256"] == expected_content_sha
    assert result["visual_asset_sha256"] == VISUAL_SHA
    assert result["source"] == "explicit_human_review"

    persisted = fake_db.collection.doc["content_dyno_review"]
    assert persisted["run_id"] == run.run_id
    assert persisted["final_content_sha256"] == expected_content_sha
    assert persisted["visual_asset_sha256"] == VISUAL_SHA


def test_client_cannot_smuggle_review_identity_fields():
    payload = review_input().model_dump(mode="python")
    payload["run_id"] = "client-controlled-run"
    payload["final_content_sha256"] = "b" * 64
    payload["visual_asset_sha256"] = "c" * 64

    with pytest.raises(ValidationError):
        HumanEditorialReviewInput.model_validate(payload)


@pytest.mark.asyncio
async def test_submit_dyno_review_fails_closed_without_ready_visual(monkeypatch):
    run = reviewable_run()
    run.visual_render = None
    fake_db = FakeDB(run.model_dump(mode="python"))
    monkeypatch.setattr(dyno_routes, "get_db", lambda: fake_db)

    with pytest.raises(HTTPException) as exc:
        await dyno_routes.submit_content_dyno_review(run.run_id, review_input())

    assert exc.value.status_code == 409
    assert "READY final visual" in exc.value.detail


@pytest.mark.asyncio
async def test_current_dyno_report_detects_stored_review_after_content_changes(monkeypatch):
    run = reviewable_run()
    input_review = review_input()
    run.content_dyno_review = HumanEditorialReview(
        run_id=run.run_id,
        final_content_sha256=hashlib.sha256(run.final_content.encode("utf-8")).hexdigest(),
        visual_asset_sha256=VISUAL_SHA,
        **input_review.model_dump(mode="python"),
    )
    run.final_content = f"{run.final_content} Changed after review."
    fake_db = FakeDB(run.model_dump(mode="python"))
    monkeypatch.setattr(dyno_routes, "get_db", lambda: fake_db)

    report = await dyno_routes.get_content_dyno_report(run.run_id)

    codes = {loss["code"] for loss in report["drivetrain_losses"]}
    assert report["signature"] == "UNSIGNED"
    assert "HUMAN_EDITORIAL_REVIEW_CONTENT_STALE" in codes
