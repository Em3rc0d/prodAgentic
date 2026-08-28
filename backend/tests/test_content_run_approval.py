import copy
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import routes.content_runs as content_runs_routes
from core.grounding import GroundingPolicy
from models.content_run import ContentRunApprovalRequest, ContentRunStatus
from models.grounding import (
    Claim,
    ClaimType,
    EvidenceRef,
    GroundingAssessment,
    GroundingReviewDecision,
    GroundingReviewSnapshot,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from routes.content_runs import approve_content_run


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc, simulate_concurrent_update=False):
        self.doc = copy.deepcopy(doc)
        self.simulate_concurrent_update = simulate_concurrent_update
        self.calls = []

    async def find_one(self, query):
        if self.doc is None or self.doc.get("run_id") != query.get("run_id"):
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update):
        self.calls.append({"query": copy.deepcopy(query), "update": copy.deepcopy(update)})

        if self.simulate_concurrent_update and "updated_at" in query:
            self.doc["updated_at"] = self.doc["updated_at"] + timedelta(seconds=1)
            self.simulate_concurrent_update = False

        if self.doc.get("run_id") != query.get("run_id"):
            return UpdateResult(0)
        if "status" in query and self.doc.get("status") != query["status"]:
            return UpdateResult(0)
        if "updated_at" in query and self.doc.get("updated_at") != query["updated_at"]:
            return UpdateResult(0)

        self.doc.update(copy.deepcopy(update.get("$set", {})))
        return UpdateResult(1)


class FakeDb:
    def __init__(self, run_doc, simulate_concurrent_update=False):
        self.content_runs = FakeCollection(run_doc, simulate_concurrent_update)

    def __getitem__(self, name):
        if name == "content_runs":
            return self.content_runs
        raise AssertionError(f"Unexpected collection: {name}")


def current_visual(prompt="visual prompt"):
    return {
        "render_id": "render-1",
        "status": "READY",
        "provider": "MockImageProvider",
        "asset_url": "/assets/renders/render-1.png",
        "asset_sha256": "a" * 64,
        "width": 1200,
        "height": 675,
        "prompt_used": prompt,
        "requested_prompt": prompt,
        "aspect_ratio": "16:9",
        "style": "minimal",
        "idempotency_key": "intent-12345678",
        "error_message": None,
        "rendered_at": datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
    }


def verified_grounding(final_content: str, *, decision=GroundingReviewDecision.VERIFIED):
    source_packet = SourcePacket(
        packet_id="packet-approval",
        workspace_id="legacy-default",
        title="Approval grounding fixture",
        evidence=[
            EvidenceRef(
                evidence_id="ev-approval",
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.PASTED_TEXT,
                excerpt="A publishable LinkedIn post.",
            )
        ],
    )
    assessment = GroundingAssessment(
        assessment_id="assessment-approval",
        packet_id=source_packet.packet_id,
        content_sha256=hashlib.sha256(final_content.encode("utf-8")).hexdigest(),
        evaluator_version="test-evaluator-v1",
        extraction_complete=True,
        claims=[
            Claim(
                claim_id="claim-approval",
                statement=final_content,
                claim_type=ClaimType.FACT,
                grounding_status=GroundingStatus.GROUNDED,
                source_refs=["ev-approval"],
                confidence=1.0,
            )
        ],
    )
    gate = GroundingPolicy.evaluate(assessment, source_packet)
    review = GroundingReviewSnapshot(
        review_id="review-approval",
        decision=decision,
        content_sha256=assessment.content_sha256,
        assessment_sha256=content_runs_routes._sha256_json(assessment.model_dump(mode="python")),
        policy_version=gate.policy_version,
        warning_claim_ids=gate.warning_claim_ids,
        reviewed_at=datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc),
    )
    return {
        "source_packet": source_packet.model_dump(mode="python"),
        "grounding_assessment": assessment.model_dump(mode="python"),
        "grounding_gate": gate.model_dump(mode="python"),
        "grounding_review": review.model_dump(mode="python"),
    }


def review_run(**overrides):
    final_content = overrides.get("final_content", "A publishable LinkedIn post.")
    doc = {
        "run_id": "run-review",
        "workspace_id": "legacy-default",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": final_content,
        "visual_prompt": "visual prompt",
        "visual_render": current_visual(),
        "approval": None,
        "updated_at": datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc),
        **verified_grounding(final_content),
    }
    doc.update(overrides)
    return doc


@pytest.mark.asyncio
async def test_text_only_approval_freezes_exact_content_and_grounding_bundle(monkeypatch):
    db = FakeDb(review_run())
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    approved = await approve_content_run(
        "run-review",
        ContentRunApprovalRequest(include_visual=False),
    )

    assert approved["status"] == ContentRunStatus.APPROVED.value
    snapshot = approved["approval"]
    assert snapshot["source"] == "explicit_user_action"
    assert snapshot["include_visual"] is False
    assert snapshot["final_content"] == "A publishable LinkedIn post."
    assert snapshot["final_content_sha256"] == hashlib.sha256(
        b"A publishable LinkedIn post."
    ).hexdigest()
    assert snapshot["visual_render"] is None
    assert snapshot["visual_render_sha256"] is None
    assert len(snapshot["source_packet_sha256"]) == 64
    assert len(snapshot["grounding_assessment_sha256"]) == 64
    assert len(snapshot["grounding_gate_sha256"]) == 64
    assert len(snapshot["grounding_review_sha256"]) == 64
    assert snapshot["grounding_policy_version"] == GroundingPolicy.VERSION
    assert len(snapshot["bundle_sha256"]) == 64


@pytest.mark.asyncio
async def test_visual_approval_freezes_current_owned_render_and_digests(monkeypatch):
    db = FakeDb(review_run())
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    approved = await approve_content_run(
        "run-review",
        ContentRunApprovalRequest(include_visual=True),
    )

    snapshot = approved["approval"]
    assert approved["status"] == ContentRunStatus.APPROVED.value
    assert snapshot["include_visual"] is True
    assert snapshot["visual_render"]["render_id"] == "render-1"
    assert snapshot["visual_render"]["asset_sha256"] == "a" * 64
    assert len(snapshot["visual_render_sha256"]) == 64
    assert len(snapshot["bundle_sha256"]) == 64


@pytest.mark.asyncio
async def test_approval_rejects_missing_grounding(monkeypatch):
    run = review_run()
    run["source_packet"] = None
    run["grounding_assessment"] = None
    run["grounding_gate"] = None
    run["grounding_review"] = None
    db = FakeDb(run)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=False),
        )

    assert exc.value.status_code == 409
    assert "Grounding" in exc.value.detail
    assert db.content_runs.doc["status"] == ContentRunStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_approval_rejects_non_verified_grounding_review(monkeypatch):
    run = review_run()
    run.update(verified_grounding(run["final_content"], decision=GroundingReviewDecision.REJECTED))
    db = FakeDb(run)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=False),
        )

    assert exc.value.status_code == 409
    assert "not VERIFIED" in exc.value.detail


@pytest.mark.asyncio
async def test_approval_rejects_stale_grounding_revision(monkeypatch):
    run = review_run()
    run["final_content"] = "Edited after Grounding verification."
    db = FakeDb(run)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=False),
        )

    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_visual_approval_rejects_render_without_asset_digest(monkeypatch):
    visual = current_visual()
    visual["asset_sha256"] = None
    db = FakeDb(review_run(visual_render=visual))
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=True),
        )

    assert exc.value.status_code == 409
    assert "immutable asset evidence" in exc.value.detail
    assert db.content_runs.doc["status"] == ContentRunStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_visual_approval_rejects_stale_prompt(monkeypatch):
    db = FakeDb(review_run(visual_prompt="new prompt"))
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=True),
        )

    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_only_ready_for_review_can_cross_approval_boundary(monkeypatch):
    db = FakeDb(review_run(status=ContentRunStatus.TEXT_READY.value))
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=False),
        )

    assert exc.value.status_code == 409
    assert "READY_FOR_REVIEW" in exc.value.detail


@pytest.mark.asyncio
async def test_concurrent_review_change_blocks_stale_approval(monkeypatch):
    db = FakeDb(review_run(), simulate_concurrent_update=True)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-review",
            ContentRunApprovalRequest(include_visual=True),
        )

    assert exc.value.status_code == 409
    assert "changed while approval" in exc.value.detail
    assert db.content_runs.doc["status"] == ContentRunStatus.READY_FOR_REVIEW.value
    assert db.content_runs.doc["approval"] is None
