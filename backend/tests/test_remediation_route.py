import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.remediation as remediation_routes
from core.grounding import source_packet_sha256
from core.remediation import grounding_assessment_sha256
from models.content_run import ContentRunStatus
from models.grounding import (
    Claim,
    ClaimType,
    EvidenceRef,
    GroundingAssessment,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.remediation import (
    ClaimRemediationProposal,
    GroundingRemediationDraft,
    RemediationAction,
)


FINAL_CONTENT = "The release improved customer trust by 40%."
CONTENT_SHA = hashlib.sha256(FINAL_CONTENT.encode("utf-8")).hexdigest()


def packet():
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Evidence",
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #410 completed successfully.",
            )
        ],
    )


def assessment():
    return GroundingAssessment(
        assessment_id="assessment-1",
        packet_id="packet-1",
        content_sha256=CONTENT_SHA,
        evaluator_version="test-v1",
        extraction_complete=True,
        claims=[
            Claim(
                claim_id="c1",
                statement=FINAL_CONTENT,
                claim_type=ClaimType.FACT,
                grounding_status=GroundingStatus.INSUFFICIENT_EVIDENCE,
                source_refs=[],
                rationale="unsupported metric",
                confidence=0.9,
            )
        ],
    )


def run_doc():
    source = packet()
    current = assessment()
    return {
        "run_id": "run-1",
        "workspace_id": "workspace-1",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": FINAL_CONTENT,
        "source_packet": source.model_dump(mode="python"),
        "grounding_assessment": current.model_dump(mode="python"),
    }


class ReadOnlyCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query):
        return self.doc


class FakeDB:
    def __init__(self, doc):
        self.collection = ReadOnlyCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def request_with(remediator):
    container = SimpleNamespace(remediator=remediator)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


class SafeFakeRemediator:
    async def remediate(self, current, source):
        return GroundingRemediationDraft(
            remediation_id="remediation-1",
            packet_id=source.packet_id,
            content_sha256=current.content_sha256,
            source_packet_sha256=source_packet_sha256(source),
            assessment_id=current.assessment_id,
            assessment_sha256=grounding_assessment_sha256(current),
            remediator_version="fake-v1",
            proposals=[
                ClaimRemediationProposal(
                    claim_id="c1",
                    action=RemediationAction.SOFTEN,
                    proposed_statement="CI #410 completed successfully.",
                    proposed_claim_type=ClaimType.FACT,
                    source_refs=["e1"],
                    rationale="Retain only evidenced state.",
                    confidence=0.9,
                )
            ],
        )


@pytest.mark.asyncio
async def test_remediation_route_is_advisory_and_never_writes(monkeypatch):
    fake_db = FakeDB(run_doc())
    monkeypatch.setattr(remediation_routes, "get_db", lambda: fake_db)

    result = await remediation_routes.propose_content_run_remediation(
        "run-1",
        request_with(SafeFakeRemediator()),
    )

    assert result["advisory_only"] is True
    assert result["auto_applied"] is False
    assert result["gate"]["valid"] is True
    assert result["requires_explicit_edit_and_full_regrounding"] is True
    assert result["draft"]["proposals"][0]["action"] == "SOFTEN"
    # Collection intentionally has no update API. Reaching here proves no write.


@pytest.mark.asyncio
async def test_remediation_route_rejects_stale_assessment(monkeypatch):
    doc = run_doc()
    doc["final_content"] = FINAL_CONTENT + " edited"
    monkeypatch.setattr(remediation_routes, "get_db", lambda: FakeDB(doc))

    with pytest.raises(HTTPException) as exc:
        await remediation_routes.propose_content_run_remediation(
            "run-1",
            request_with(SafeFakeRemediator()),
        )

    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail


@pytest.mark.asyncio
async def test_remediation_route_requires_ready_for_review(monkeypatch):
    doc = run_doc()
    doc["status"] = ContentRunStatus.TEXT_READY.value
    monkeypatch.setattr(remediation_routes, "get_db", lambda: FakeDB(doc))

    with pytest.raises(HTTPException) as exc:
        await remediation_routes.propose_content_run_remediation(
            "run-1",
            request_with(SafeFakeRemediator()),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_remediation_route_fails_closed_without_provider(monkeypatch):
    monkeypatch.setattr(remediation_routes, "get_db", lambda: FakeDB(run_doc()))

    with pytest.raises(HTTPException) as exc:
        await remediation_routes.propose_content_run_remediation(
            "run-1",
            request_with(None),
        )

    assert exc.value.status_code == 503
