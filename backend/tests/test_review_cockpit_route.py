from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.review_cockpit as cockpit_routes
from models.claim_extractor import (
    ClaimExtractionOutput,
    ClaimExtractionReviewDecision,
    ClaimExtractionReviewSnapshot,
    claim_extraction_sha256,
)
from models.content_run import ContentRunStatus
from models.grounding import (
    ClaimProposal,
    ClaimType,
    EvidenceMatchProposal,
    EvidenceRef,
    EvidenceRelation,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.semantic_matcher import SemanticMatcherOutput


class FakeCollection:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    async def find_one(self, query):
        return self.doc

    async def update_one(self, query, update):
        self.updates.append((query, update))
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


def packet(*, title="Immutable evidence") -> SourcePacket:
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title=title,
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #608 completed successfully.",
            )
        ],
    )


def reviewed_doc(content="CI #608 completed successfully."):
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    claim = ClaimProposal(
        claim_id="c1",
        statement=content,
        claim_type=ClaimType.FACT,
        confidence=0.99,
        text_start=0,
        text_end=len(content),
    )
    extraction = ClaimExtractionOutput(
        extraction_id="extract-1",
        content_sha256=content_sha,
        extractor_version="claim-extractor-test-v1",
        claims=[claim],
    )
    extraction_review = ClaimExtractionReviewSnapshot(
        review_id="extract-review-1",
        decision=ClaimExtractionReviewDecision.VERIFIED_COMPLETE,
        extraction_id=extraction.extraction_id,
        content_sha256=content_sha,
        extraction_sha256=claim_extraction_sha256(extraction),
    )
    return {
        "run_id": "run-1",
        "workspace_id": "workspace-1",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": content,
        "generation_source_packet": packet().model_dump(mode="python"),
        "claim_extraction": extraction.model_dump(mode="python"),
        "claim_extraction_review": extraction_review.model_dump(mode="python"),
        "updated_at": "revision-1",
    }


def app_request(matcher):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(container=SimpleNamespace(semantic_matcher=matcher))
        )
    )


class SupportingMatcher:
    async def match(self, matcher_input, source_packet):
        assert matcher_input.packet_id == "packet-1"
        assert [claim.claim_id for claim in matcher_input.claims] == ["c1"]
        return SemanticMatcherOutput(
            match_id="match-1",
            packet_id=source_packet.packet_id,
            content_sha256=matcher_input.content_sha256,
            matcher_version="semantic-provider-test-v1",
            evidence_matches=[
                EvidenceMatchProposal(
                    claim_id="c1",
                    evidence_id="e1",
                    relation=EvidenceRelation.SUPPORTS,
                    confidence=0.98,
                    rationale="The evidence directly states the claim.",
                )
            ],
        )


@pytest.mark.asyncio
async def test_match_evaluate_current_uses_server_owned_generation_packet_and_persists_chain(monkeypatch):
    doc = reviewed_doc()
    fake_db = FakeDB(doc)
    immutable_packet = packet()

    class FakeRepository:
        def __init__(self, db):
            assert db is fake_db

        async def get(self, workspace_id, packet_id):
            assert (workspace_id, packet_id) == ("workspace-1", "packet-1")
            return immutable_packet

    monkeypatch.setattr(cockpit_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(cockpit_routes, "SourcePacketRepository", FakeRepository)

    result = await cockpit_routes.match_evaluate_current_generation_evidence(
        "run-1",
        app_request(SupportingMatcher()),
    )

    assert result["draft"]["packet_id"] == "packet-1"
    assert result["assessment"]["claims"][0]["grounding_status"] == "GROUNDED"
    assert result["gate"]["decision"] == "PASS"
    persisted = fake_db.collection.doc
    assert persisted["grounding_match_draft"]["draft_id"] == result["draft"]["draft_id"]
    assert persisted["source_packet"]["packet_id"] == "packet-1"
    assert persisted["grounding_assessment"]["assessment_id"] == result["assessment"]["assessment_id"]
    assert persisted["grounding_gate"]["decision"] == "PASS"
    assert persisted["grounding_review"] is None


@pytest.mark.asyncio
async def test_match_evaluate_current_rejects_non_evidence_fed_run(monkeypatch):
    doc = reviewed_doc()
    doc["generation_source_packet"] = None
    monkeypatch.setattr(cockpit_routes, "get_db", lambda: FakeDB(doc))

    with pytest.raises(HTTPException) as exc:
        await cockpit_routes.match_evaluate_current_generation_evidence(
            "run-1",
            app_request(SupportingMatcher()),
        )

    assert exc.value.status_code == 409
    assert "Evidence-fed generation SourcePacket" in exc.value.detail


@pytest.mark.asyncio
async def test_match_evaluate_current_rejects_packet_snapshot_drift(monkeypatch):
    doc = reviewed_doc()
    fake_db = FakeDB(doc)

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            return packet(title="Mutated repository packet")

    monkeypatch.setattr(cockpit_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(cockpit_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await cockpit_routes.match_evaluate_current_generation_evidence(
            "run-1",
            app_request(SupportingMatcher()),
        )

    assert exc.value.status_code == 409
    assert "immutable repository snapshot" in exc.value.detail
    assert fake_db.collection.updates == []


@pytest.mark.asyncio
async def test_match_evaluate_current_requires_human_verified_complete_extraction(monkeypatch):
    doc = reviewed_doc()
    doc["claim_extraction_review"] = None
    monkeypatch.setattr(cockpit_routes, "get_db", lambda: FakeDB(doc))

    with pytest.raises(HTTPException) as exc:
        await cockpit_routes.match_evaluate_current_generation_evidence(
            "run-1",
            app_request(SupportingMatcher()),
        )

    assert exc.value.status_code == 409
    assert "Verified claim extraction" in exc.value.detail


@pytest.mark.asyncio
async def test_match_evaluate_current_fails_closed_without_matcher(monkeypatch):
    doc = reviewed_doc()
    fake_db = FakeDB(doc)

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            return packet()

    monkeypatch.setattr(cockpit_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(cockpit_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await cockpit_routes.match_evaluate_current_generation_evidence(
            "run-1",
            app_request(None),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Semantic matcher provider is unavailable"
