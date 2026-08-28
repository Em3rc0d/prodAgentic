import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.claim_extractor as claim_routes
from models.claim_extractor import (
    ClaimExtractionOutput,
    ClaimExtractionReviewDecision,
    ClaimExtractionReviewRequest,
    claim_extraction_sha256,
)
from models.content_run import ContentRunStatus
from models.grounding import ClaimProposal, ClaimType


class UpdateResult:
    def __init__(self, matched_count=1):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    async def find_one(self, query):
        return self.doc

    async def update_one(self, query, update):
        self.updates.append((query, update))
        for key, value in update.get("$set", {}).items():
            self.doc[key] = value
        return UpdateResult(1)


class FakeDB:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def base_doc(content="CI #376 passed all four gates."):
    return {
        "run_id": "run-1",
        "workspace_id": "workspace-1",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "final_content": content,
        "updated_at": "revision-1",
        "grounding_assessment": {"old": True},
        "grounding_gate": {"old": True},
        "grounding_review": {"old": True},
    }


def extraction_for(content):
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ClaimExtractionOutput(
        extraction_id="extract-1",
        content_sha256=sha,
        extractor_version="test-extractor-v1",
        claims=[
            ClaimProposal(
                claim_id="c1",
                statement=content,
                claim_type=ClaimType.FACT,
                confidence=0.9,
                text_start=0,
                text_end=len(content),
            )
        ],
    )


def app_request(extractor):
    container = SimpleNamespace(claim_extractor=extractor)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


@pytest.mark.asyncio
async def test_extract_claims_persists_advisory_snapshot_and_invalidates_downstream(monkeypatch):
    doc = base_doc()
    db = FakeDB(doc)
    extraction = extraction_for(doc["final_content"])

    class FakeExtractor:
        async def extract(self, *, content, content_sha256):
            assert content == doc["final_content"]
            assert content_sha256 == extraction.content_sha256
            return extraction

    monkeypatch.setattr(claim_routes, "get_db", lambda: db)

    result = await claim_routes.extract_content_run_claims(
        "run-1",
        app_request(FakeExtractor()),
    )

    assert result["extraction_id"] == "extract-1"
    assert result["requires_human_completeness_review"] is True
    assert db.collection.doc["claim_extraction"]["extraction_id"] == "extract-1"
    assert db.collection.doc["claim_extraction_review"] is None
    assert db.collection.doc["grounding_assessment"] is None
    assert db.collection.doc["grounding_gate"] is None
    assert db.collection.doc["grounding_review"] is None


@pytest.mark.asyncio
async def test_extract_claims_fails_closed_without_provider(monkeypatch):
    db = FakeDB(base_doc())
    monkeypatch.setattr(claim_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await claim_routes.extract_content_run_claims("run-1", app_request(None))

    assert exc.value.status_code == 503
    assert exc.value.detail == "Claim extractor provider is unavailable"


@pytest.mark.asyncio
async def test_human_review_binds_exact_extraction_digest(monkeypatch):
    doc = base_doc()
    extraction = extraction_for(doc["final_content"])
    doc["claim_extraction"] = extraction.model_dump(mode="python")
    db = FakeDB(doc)
    monkeypatch.setattr(claim_routes, "get_db", lambda: db)

    result = await claim_routes.review_content_run_claim_extraction(
        "run-1",
        ClaimExtractionReviewRequest(
            decision=ClaimExtractionReviewDecision.VERIFIED_COMPLETE
        ),
    )

    assert result["decision"] == "VERIFIED_COMPLETE"
    assert result["extraction_id"] == extraction.extraction_id
    assert result["content_sha256"] == extraction.content_sha256
    assert result["extraction_sha256"] == claim_extraction_sha256(extraction)


@pytest.mark.asyncio
async def test_human_review_rejects_stale_extraction(monkeypatch):
    doc = base_doc()
    extraction = extraction_for(doc["final_content"])
    doc["claim_extraction"] = extraction.model_dump(mode="python")
    doc["final_content"] = "Edited after extraction."
    db = FakeDB(doc)
    monkeypatch.setattr(claim_routes, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await claim_routes.review_content_run_claim_extraction(
            "run-1",
            ClaimExtractionReviewRequest(
                decision=ClaimExtractionReviewDecision.VERIFIED_COMPLETE
            ),
        )

    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()


def test_verified_extraction_rejects_tampered_snapshot():
    doc = base_doc()
    extraction = extraction_for(doc["final_content"])
    doc["claim_extraction"] = extraction.model_dump(mode="python")

    import uuid
    from models.claim_extractor import ClaimExtractionReviewSnapshot

    review = ClaimExtractionReviewSnapshot(
        review_id=str(uuid.uuid4()),
        decision=ClaimExtractionReviewDecision.VERIFIED_COMPLETE,
        extraction_id=extraction.extraction_id,
        content_sha256=extraction.content_sha256,
        extraction_sha256=claim_extraction_sha256(extraction),
    )
    doc["claim_extraction_review"] = review.model_dump(mode="python")

    # Tamper the persisted extraction after review without updating its review.
    doc["claim_extraction"]["claims"][0]["statement"] = "Fabricated replacement claim"

    with pytest.raises(HTTPException) as exc:
        claim_routes.require_verified_claim_extraction(doc)

    assert exc.value.status_code == 409
    assert "changed after human" in exc.value.detail


def test_rejected_extraction_cannot_feed_matcher():
    doc = base_doc()
    extraction = extraction_for(doc["final_content"])
    doc["claim_extraction"] = extraction.model_dump(mode="python")

    from models.claim_extractor import ClaimExtractionReviewSnapshot

    review = ClaimExtractionReviewSnapshot(
        review_id="review-1",
        decision=ClaimExtractionReviewDecision.REJECTED,
        extraction_id=extraction.extraction_id,
        content_sha256=extraction.content_sha256,
        extraction_sha256=claim_extraction_sha256(extraction),
    )
    doc["claim_extraction_review"] = review.model_dump(mode="python")

    with pytest.raises(HTTPException) as exc:
        claim_routes.require_verified_claim_extraction(doc)

    assert exc.value.status_code == 409
    assert "not VERIFIED_COMPLETE" in exc.value.detail
