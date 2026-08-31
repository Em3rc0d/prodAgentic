from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.semantic_matcher as semantic_routes
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
from models.semantic_matcher import SemanticMatchDraftRequest, SemanticMatcherOutput


class FakeCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query):
        return self.doc


class FakeDB:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def packet(workspace_id="workspace-1"):
    return SourcePacket(
        packet_id="packet-1",
        workspace_id=workspace_id,
        title="Evidence",
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SOURCE_SNAPSHOT,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #356 completed successfully.",
            )
        ],
    )


def request_body():
    return SemanticMatchDraftRequest(packet_id="packet-1")


def reviewed_doc(content="CI #356 completed successfully."):
    claim = ClaimProposal(
        claim_id="c1",
        statement=content,
        claim_type=ClaimType.FACT,
        confidence=0.95,
        text_start=0,
        text_end=len(content),
    )
    import hashlib

    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    extraction = ClaimExtractionOutput(
        extraction_id="extract-1",
        content_sha256=content_sha,
        extractor_version="test-extractor-v1",
        claims=[claim],
    )
    review = ClaimExtractionReviewSnapshot(
        review_id="review-1",
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
        "claim_extraction": extraction.model_dump(mode="python"),
        "claim_extraction_review": review.model_dump(mode="python"),
    }


def app_request(matcher):
    container = SimpleNamespace(semantic_matcher=matcher)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


@pytest.mark.asyncio
async def test_match_draft_uses_server_reviewed_claims_and_does_not_persist(monkeypatch):
    doc = reviewed_doc()
    fake_db = FakeDB(doc)
    source_packet = packet()

    class FakeRepository:
        def __init__(self, db):
            assert db is fake_db

        async def get(self, workspace_id, packet_id):
            assert (workspace_id, packet_id) == ("workspace-1", "packet-1")
            return source_packet

    class FakeMatcher:
        async def match(self, matcher_input, packet_arg):
            assert packet_arg is source_packet
            assert [claim.claim_id for claim in matcher_input.claims] == ["c1"]
            return SemanticMatcherOutput(
                match_id="m1",
                packet_id=packet_arg.packet_id,
                content_sha256=matcher_input.content_sha256,
                matcher_version="fake-real-provider-v1",
                evidence_matches=[
                    EvidenceMatchProposal(
                        claim_id="c1",
                        evidence_id="e1",
                        relation=EvidenceRelation.SUPPORTS,
                        confidence=0.9,
                    )
                ],
            )

    monkeypatch.setattr(semantic_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(semantic_routes, "SourcePacketRepository", FakeRepository)

    result = await semantic_routes.match_content_run_grounding_draft(
        "run-1",
        request_body(),
        app_request(FakeMatcher()),
    )

    assert result["packet_id"] == "packet-1"
    assert result["claims"][0]["claim_id"] == "c1"
    assert result["evidence_matches"][0]["relation"] == "SUPPORTS"
    assert result["extraction_complete"] is True
    assert "fake-real-provider-v1" in result["evaluator_version"]
    # FakeCollection intentionally implements no write API. Reaching this point
    # proves the provider-facing route did not persist Grounding authority.


@pytest.mark.asyncio
async def test_match_draft_rejects_missing_human_completeness_review(monkeypatch):
    doc = reviewed_doc()
    doc["claim_extraction_review"] = None
    fake_db = FakeDB(doc)
    monkeypatch.setattr(semantic_routes, "get_db", lambda: fake_db)

    with pytest.raises(HTTPException) as exc:
        await semantic_routes.match_content_run_grounding_draft(
            "run-1",
            request_body(),
            app_request(object()),
        )

    assert exc.value.status_code == 409
    assert "Verified claim extraction" in exc.value.detail


@pytest.mark.asyncio
async def test_match_draft_rejects_stale_claim_extraction(monkeypatch):
    doc = reviewed_doc()
    doc["final_content"] += " Edited."
    fake_db = FakeDB(doc)
    monkeypatch.setattr(semantic_routes, "get_db", lambda: fake_db)

    with pytest.raises(HTTPException) as exc:
        await semantic_routes.match_content_run_grounding_draft(
            "run-1",
            request_body(),
            app_request(object()),
        )

    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_match_draft_scopes_source_packet_to_run_workspace(monkeypatch):
    doc = reviewed_doc("Content")
    fake_db = FakeDB(doc)
    calls = []

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            calls.append((workspace_id, packet_id))
            return None

    monkeypatch.setattr(semantic_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(semantic_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await semantic_routes.match_content_run_grounding_draft(
            "run-1",
            request_body(),
            app_request(object()),
        )

    assert calls == [("workspace-1", "packet-1")]
    assert exc.value.status_code == 404
    assert exc.value.detail == "Source packet not found"


@pytest.mark.asyncio
async def test_match_draft_fails_closed_without_provider(monkeypatch):
    doc = reviewed_doc("Content")
    fake_db = FakeDB(doc)

    class FakeRepository:
        def __init__(self, db):
            pass

        async def get(self, workspace_id, packet_id):
            return packet()

    monkeypatch.setattr(semantic_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(semantic_routes, "SourcePacketRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        await semantic_routes.match_content_run_grounding_draft(
            "run-1",
            request_body(),
            app_request(None),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Semantic matcher provider is unavailable"


@pytest.mark.asyncio
async def test_match_draft_requires_ready_for_review(monkeypatch):
    doc = reviewed_doc("Content")
    doc["status"] = ContentRunStatus.TEXT_READY.value
    monkeypatch.setattr(semantic_routes, "get_db", lambda: FakeDB(doc))

    with pytest.raises(HTTPException) as exc:
        await semantic_routes.match_content_run_grounding_draft(
            "run-1",
            request_body(),
            app_request(object()),
        )

    assert exc.value.status_code == 409
