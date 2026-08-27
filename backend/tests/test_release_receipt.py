from datetime import datetime, timedelta, timezone

from tools.release_receipt import _hash_identifier, _publication_checks


def test_release_receipt_hashes_linkedin_identity_instead_of_exposing_it():
    raw = "urn:li:person:123456"
    digest = _hash_identifier(raw)

    assert digest
    assert raw not in digest
    assert len(digest) == 64


def test_publication_receipt_validates_immutable_evidence_without_plaintext_content():
    text = "immutable approved content"
    import hashlib
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    author = "urn:li:person:123"
    from core.publication import _publication_dedupe_key

    run = {
        "run_id": "run-1",
        "workspace_id": "workspace-a",
        "status": "PUBLISHED",
        "approval": {
            "approval_id": "approval-1",
            "bundle_sha256": "bundle-1",
            "final_content": text,
            "final_content_sha256": text_sha,
            "include_visual": False,
        },
        "publication": {
            "status": "PUBLISHED",
            "attempt_id": "attempt-1",
            "bundle_sha256": "bundle-1",
            "content_sha256": text_sha,
            "author_urn": author,
            "dedupe_key": _publication_dedupe_key(author, text_sha),
            "external_post_urn": "urn:li:share:999",
            "external_image_urn": None,
            "completed_at": datetime.now(timezone.utc),
        },
    }
    oauth = {
        "author_urn": author,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }

    checks, receipt = _publication_checks(run, oauth)

    assert all(checks.values())
    assert receipt["run_id"] == "run-1"
    assert receipt["external_post_urn"] == "urn:li:share:999"
    assert receipt["author_urn_sha256"] == _hash_identifier(author)
    assert "final_content" not in receipt
    assert text not in str(receipt)
    assert author not in str(receipt)
