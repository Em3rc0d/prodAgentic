import copy
import hashlib
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import routes.content_runs as content_runs_routes
from core.grounding import GroundingPolicy
from models.content_run import ContentRunApprovalRequest, ContentRunStatus
from models.grounding import (
    Claim,
    ClaimProposal,
    ClaimType,
    EvidenceMatchProposal,
    EvidenceRef,
    EvidenceRelation,
    GroundingAssessment,
    GroundingDraftEvaluationRequest,
    GroundingEvaluationDraft,
    GroundingEvaluationRequest,
    GroundingReviewDecision,
    GroundingReviewRequest,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from routes.content_runs import (
    approve_content_run,
    evaluate_content_run_grounding,
    evaluate_content_run_grounding_draft,
    review_content_run_grounding,
)


class UpdateResult:
    def __init__(self, matched_count: int):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc):
        self.doc = copy.deepcopy(doc)

    async def find_one(self, query):
        if self.doc is None:
            return None
        if "run_id" in query and self.doc.get("run_id") != query["run_id"]:
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update, **_kwargs):
        if self.doc is None or self.doc.get("run_id") != query.get("run_id"):
            return UpdateResult(0)
        if "status" in query and self.doc.get("status") != query["status"]:
            return UpdateResult(0)
        if "updated_at" in query and self.doc.get("updated_at") != query["updated_at"]:
            return UpdateResult(0)
        self.doc.update(copy.deepcopy(update.get("$set", {})))
        return UpdateResult(1)


class FakeMemoryService:
    def __init__(self, db=None):
        self.db = db

    async def refresh_review(self, run_id):
        doc = self.db["content_runs"].doc
        final = doc["final_content"]
        identity = content_runs_routes.build_content_identity(final)
        doc["memory_check"] = {
            "normalized_sha256": identity.normalized_sha256,
        }
        return True


class FakeDb:
    def __init__(self, run):
        self.collections = {
            "content_runs": FakeCollection(run),
        }

    def __getitem__(self, name):
        if name not in self.collections:
            raise AssertionError(f"Unexpected collection: {name}")
        return self.collections[name]


def review_run(final_content="Two tests failed."):
    return {
        "run_id": "run-grounding",
        "workspace_id": "workspace-1",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": final_content,
        "visual_prompt": None,
        "visual_render": None,
        "source_packet": None,
        "grounding_assessment": None,
        "grounding_gate": None,
        "grounding_review": None,
        "memory_check": None,
        "approval": None,
        "updated_at": datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
    }


def source_packet(workspace_id="workspace-1"):
    return SourcePacket(
        packet_id="packet-1",
        workspace_id=workspace_id,
        title="CI evidence",
        evidence=[
            EvidenceRef(
                evidence_id="ev-1",
                authority=SourceAuthority.SYSTEM_DERIVED,
                source_type=SourceType.CI_EVIDENCE,
                locator="github-actions://run/33127455899",
                excerpt="150 passed, 2 failed",
            )
        ],
    )


def grounding_request(
    final_content="Two tests failed.",
    *,
    workspace_id="workspace-1",
    status=GroundingStatus.GROUNDED,
    statement="Two tests failed.",
):
    packet = source_packet(workspace_id)
    assessment = GroundingAssessment(
        assessment_id="assessment-1",
        packet_id=packet.packet_id,
        content_sha256=hashlib.sha256(final_content.encode("utf-8")).hexdigest(),
        evaluator_version="fixture-v1",
        extraction_complete=True,
        claims=[
            Claim(
                claim_id="claim-1",
                statement=statement,
                claim_type=ClaimType.FACT,
                grounding_status=status,
                source_refs=["ev-1"] if status != GroundingStatus.INSUFFICIENT_EVIDENCE else [],
                confidence=1.0,
            )
        ],
    )
    return GroundingEvaluationRequest(source_packet=packet, assessment=assessment)


def grounding_draft_request(final_content="Two tests failed."):
    packet = source_packet()
    draft = GroundingEvaluationDraft(
        draft_id="draft-1",
        packet_id=packet.packet_id,
        content_sha256=hashlib.sha256(final_content.encode("utf-8")).hexdigest(),
        evaluator_version="semantic-proposal-fixture-v1",
        extraction_complete=True,
        claims=[
            ClaimProposal(
                claim_id="claim-1",
                statement=final_content,
                claim_type=ClaimType.FACT,
                confidence=0.95,
                text_start=0,
                text_end=len(final_content),
            )
        ],
        evidence_matches=[
            EvidenceMatchProposal(
                claim_id="claim-1",
                evidence_id="ev-1",
                relation=EvidenceRelation.SUPPORTS,
                confidence=0.9,
                rationale="The evidence directly states that two tests failed.",
            )
        ],
    )
    return GroundingDraftEvaluationRequest(source_packet=packet, draft=draft)


def install_db(monkeypatch, run):
    db = FakeDb(run)
    monkeypatch.setattr(content_runs_routes, "get_db", lambda: db)
    monkeypatch.setattr(content_runs_routes, "ContentMemoryService", FakeMemoryService)
    return db


@pytest.mark.asyncio
async def test_exact_revision_grounding_persists_pass_and_clears_old_human_review(monkeypatch):
    run = review_run()
    run["grounding_review"] = {
        "review_id": "old-review",
        "decision": "VERIFIED",
        "source": "explicit_user_action",
        "content_sha256": "a" * 64,
        "source_packet_sha256": "c" * 64,
        "assessment_sha256": "b" * 64,
        "policy_version": GroundingPolicy.VERSION,
        "warning_claim_ids": [],
        "reviewed_at": datetime(2026, 8, 28, 13, 0, tzinfo=timezone.utc),
    }
    db = install_db(monkeypatch, run)

    updated = await evaluate_content_run_grounding("run-grounding", grounding_request())

    assert updated["grounding_gate"]["decision"] == "PASS"
    assert updated["grounding_review"] is None
    assert db["content_runs"].doc["source_packet"]["workspace_id"] == "workspace-1"


@pytest.mark.asyncio
async def test_draft_route_derives_grounded_state_instead_of_accepting_grounding_status(monkeypatch):
    db = install_db(monkeypatch, review_run())

    updated = await evaluate_content_run_grounding_draft(
        "run-grounding",
        grounding_draft_request(),
    )

    assert updated["grounding_assessment"]["claims"][0]["grounding_status"] == "GROUNDED"
    assert updated["grounding_assessment"]["claims"][0]["source_refs"] == ["ev-1"]
    assert updated["grounding_gate"]["decision"] == "PASS"
    assert updated["grounding_review"] is None
    assert "grounding-assessment-builder-v1" in updated["grounding_assessment"]["evaluator_version"]
    assert db["content_runs"].doc["source_packet"]["packet_id"] == "packet-1"


@pytest.mark.asyncio
async def test_grounding_rejects_assessment_for_previous_content_revision(monkeypatch):
    install_db(monkeypatch, review_run(final_content="Current copy."))
    stale = grounding_request(final_content="Previous copy.")

    with pytest.raises(HTTPException) as exc:
        await evaluate_content_run_grounding("run-grounding", stale)

    assert exc.value.status_code == 409
    assert "does not match current final content" in exc.value.detail


@pytest.mark.asyncio
async def test_grounding_rejects_cross_workspace_source_packet(monkeypatch):
    install_db(monkeypatch, review_run())

    with pytest.raises(HTTPException) as exc:
        await evaluate_content_run_grounding(
            "run-grounding",
            grounding_request(workspace_id="workspace-other"),
        )

    assert exc.value.status_code == 409
    assert "workspace" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_blocked_assessment_is_inspectable_but_cannot_be_human_verified(monkeypatch):
    db = install_db(monkeypatch, review_run(final_content="Reliability improved by 73 percent."))
    request = grounding_request(
        final_content="Reliability improved by 73 percent.",
        status=GroundingStatus.INSUFFICIENT_EVIDENCE,
        statement="Reliability improved by 73 percent.",
    )

    evaluated = await evaluate_content_run_grounding("run-grounding", request)
    assert evaluated["grounding_gate"]["decision"] == "BLOCK"
    assert db["content_runs"].doc["grounding_assessment"] is not None

    with pytest.raises(HTTPException) as exc:
        await review_content_run_grounding(
            "run-grounding",
            GroundingReviewRequest(decision=GroundingReviewDecision.VERIFIED),
        )

    assert exc.value.status_code == 409
    assert "policy is BLOCK" in exc.value.detail


@pytest.mark.asyncio
async def test_human_verification_is_bound_to_content_source_packet_and_assessment_hashes(monkeypatch):
    install_db(monkeypatch, review_run())
    await evaluate_content_run_grounding("run-grounding", grounding_request())

    reviewed = await review_content_run_grounding(
        "run-grounding",
        GroundingReviewRequest(decision=GroundingReviewDecision.VERIFIED),
    )

    review = reviewed["grounding_review"]
    assert review["decision"] == "VERIFIED"
    assert review["content_sha256"] == hashlib.sha256(b"Two tests failed.").hexdigest()
    expected_source_sha = content_runs_routes._sha256_json(reviewed["source_packet"])
    expected_assessment_sha = content_runs_routes._sha256_json(reviewed["grounding_assessment"])
    assert review["source_packet_sha256"] == expected_source_sha
    assert review["assessment_sha256"] == expected_assessment_sha
    assert review["policy_version"] == GroundingPolicy.VERSION


@pytest.mark.asyncio
async def test_approval_recomputes_policy_and_ignores_tampered_stored_pass(monkeypatch):
    run = review_run(final_content="Reliability improved by 73 percent.")
    db = install_db(monkeypatch, run)
    request = grounding_request(
        final_content=run["final_content"],
        status=GroundingStatus.INSUFFICIENT_EVIDENCE,
        statement=run["final_content"],
    )
    await evaluate_content_run_grounding("run-grounding", request)

    # Simulate direct database tampering. Approval must recompute the policy from
    # source_packet + assessment rather than trusting the stored gate snapshot.
    db["content_runs"].doc["grounding_gate"] = {
        "policy_version": GroundingPolicy.VERSION,
        "decision": "PASS",
        "blocking_claim_ids": [],
        "warning_claim_ids": [],
        "reasons": [],
    }
    source_packet_sha = content_runs_routes._sha256_json(db["content_runs"].doc["source_packet"])
    assessment_sha = content_runs_routes._sha256_json(db["content_runs"].doc["grounding_assessment"])
    db["content_runs"].doc["grounding_review"] = {
        "review_id": "tampered-review",
        "decision": "VERIFIED",
        "source": "explicit_user_action",
        "content_sha256": hashlib.sha256(run["final_content"].encode("utf-8")).hexdigest(),
        "source_packet_sha256": source_packet_sha,
        "assessment_sha256": assessment_sha,
        "policy_version": GroundingPolicy.VERSION,
        "warning_claim_ids": [],
        "reviewed_at": datetime(2026, 8, 28, 14, 5, tzinfo=timezone.utc),
    }

    with pytest.raises(HTTPException) as exc:
        await approve_content_run(
            "run-grounding",
            ContentRunApprovalRequest(include_visual=False),
        )

    assert exc.value.status_code == 409
    assert "Grounding BLOCK" in exc.value.detail
    assert db["content_runs"].doc["approval"] is None