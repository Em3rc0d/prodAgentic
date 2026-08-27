"""Generate a sanitized Commercial V1 runtime receipt from persisted prodAgentic state.

This command performs no LinkedIn HTTP requests and never prints OAuth tokens,
authorization codes, state values, client secrets, session cookies, or plaintext
content. It verifies the already-persisted OAuth/publication evidence instead of
creating another external side effect.

Usage inside the backend runtime/container:

    python tools/release_receipt.py
    python tools/release_receipt.py --run-id <published-run-id>

Exit code 0 means every receipt check passed. Exit code 1 means evidence is
missing/inconsistent. Configuration/database errors use exit code 2.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from core.assets import get_asset_root
from core.linkedin_oauth import LinkedInOAuthService, LinkedInOAuthSettings
from core.publication import _content_fingerprint, _publication_dedupe_key


REQUIRED_SCOPES = {"openid", "profile", "w_member_social"}
RECEIPT_VERSION = "commercial-v1-runtime-receipt-v1"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    dt = _utc(value)
    return dt.isoformat() if dt else None


def _hash_identifier(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verify_visual_asset(approval: dict[str, Any]) -> tuple[bool, str]:
    if not approval.get("include_visual"):
        return True, "not-applicable"

    visual = approval.get("visual_render")
    if not isinstance(visual, dict):
        return False, "approved visual snapshot missing"
    expected = visual.get("asset_sha256")
    asset_url = visual.get("asset_url")
    if not isinstance(expected, str) or not expected:
        return False, "approved visual digest missing"
    if not isinstance(asset_url, str) or not asset_url.startswith("/assets/"):
        return False, "approved visual asset URL is not locally owned"

    root = get_asset_root()
    path = (root / asset_url.removeprefix("/assets/")).resolve()
    if root not in path.parents or not path.is_file():
        return False, "approved visual bytes are unavailable in configured asset storage"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        return False, "approved visual digest does not match stored bytes"
    return True, "verified"


def _publication_checks(run: dict[str, Any], oauth_status: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    approval = run.get("approval") if isinstance(run.get("approval"), dict) else {}
    publication = run.get("publication") if isinstance(run.get("publication"), dict) else {}

    final_content = approval.get("final_content")
    calculated_text_sha = (
        hashlib.sha256(final_content.encode("utf-8")).hexdigest()
        if isinstance(final_content, str) and final_content
        else None
    )
    approval_text_sha = approval.get("final_content_sha256")
    publication_text_sha = publication.get("content_sha256")
    fingerprint = None
    try:
        fingerprint = _content_fingerprint(approval)
    except Exception:
        pass

    author_urn = publication.get("author_urn")
    expected_dedupe = (
        _publication_dedupe_key(author_urn, fingerprint)
        if isinstance(author_urn, str) and author_urn and isinstance(fingerprint, str) and fingerprint
        else None
    )

    visual_ok, visual_evidence = _verify_visual_asset(approval)
    oauth_author = oauth_status.get("author_urn")

    checks = {
        "root_status_published": run.get("status") == "PUBLISHED",
        "publication_status_published": publication.get("status") == "PUBLISHED",
        "immutable_approval_present": bool(approval.get("approval_id") and approval.get("bundle_sha256")),
        "bundle_identity_matches": publication.get("bundle_sha256") == approval.get("bundle_sha256"),
        "text_digest_matches_approval": bool(calculated_text_sha and calculated_text_sha == approval_text_sha),
        "text_digest_matches_publication": bool(calculated_text_sha and calculated_text_sha == publication_text_sha),
        "external_post_receipt_present": bool(publication.get("external_post_urn")),
        "author_matches_connected_oauth_identity": bool(author_urn and oauth_author and author_urn == oauth_author),
        "dedupe_key_matches_author_and_content": bool(expected_dedupe and expected_dedupe == publication.get("dedupe_key")),
        "approved_visual_bytes_verified": visual_ok,
    }

    receipt = {
        "run_id": run.get("run_id"),
        "workspace_id": run.get("workspace_id") or "legacy-default",
        "approval_id": approval.get("approval_id"),
        "bundle_sha256": approval.get("bundle_sha256"),
        "final_content_sha256": approval_text_sha,
        "publication_attempt_id": publication.get("attempt_id"),
        "publication_completed_at": _iso(publication.get("completed_at")),
        "external_post_urn": publication.get("external_post_urn"),
        "external_image_urn": publication.get("external_image_urn"),
        "author_urn_sha256": _hash_identifier(author_urn),
        "visual_evidence": visual_evidence,
    }
    return checks, receipt


async def build_receipt(run_id: str | None = None) -> dict[str, Any]:
    mongo_uri = os.environ.get("MONGO_URI", "").strip()
    database_name = os.environ.get("MONGO_DB", "content_engine").strip() or "content_engine"
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is required")

    settings = LinkedInOAuthSettings.from_env()
    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        oauth_status = await LinkedInOAuthService(db, settings=settings).status()

        query: dict[str, Any] = {
            "status": "PUBLISHED",
            "publication.status": "PUBLISHED",
        }
        if run_id:
            query["run_id"] = run_id
        run = await db["content_runs"].find_one(query, sort=[("publication.completed_at", -1)])

        oauth_scopes = set(oauth_status.get("scopes") or [])
        oauth_checks = {
            "configured": oauth_status.get("configured") is True,
            "connected": oauth_status.get("connected") is True,
            "status_connected": oauth_status.get("status") == "CONNECTED",
            "required_scopes_present": REQUIRED_SCOPES.issubset(oauth_scopes),
            "token_not_expired": bool(
                _utc(oauth_status.get("expires_at"))
                and _utc(oauth_status.get("expires_at")) > datetime.now(timezone.utc)
            ),
        }

        receipt: dict[str, Any] = {
            "receipt_version": RECEIPT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "persisted-evidence-only-no-linkedin-http",
            "oauth": {
                "status": oauth_status.get("status"),
                "connected": oauth_status.get("connected") is True,
                "scopes": sorted(oauth_scopes),
                "expires_at": _iso(oauth_status.get("expires_at")),
                "api_version": oauth_status.get("api_version"),
                "author_urn_sha256": _hash_identifier(oauth_status.get("author_urn")),
                "checks": oauth_checks,
            },
            "publication": None,
            "overall": "FAIL",
        }

        if run is None:
            receipt["publication"] = {
                "checks": {"published_run_found": False},
                "requested_run_id": run_id,
            }
            return receipt

        publication_checks, publication_receipt = _publication_checks(run, oauth_status)
        publication_receipt["checks"] = {"published_run_found": True, **publication_checks}
        receipt["publication"] = publication_receipt

        all_checks = list(oauth_checks.values()) + list(publication_receipt["checks"].values())
        receipt["overall"] = "PASS" if all(all_checks) else "FAIL"
        return receipt
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a sanitized prodAgentic Commercial V1 runtime receipt")
    parser.add_argument("--run-id", help="Specific already-published ContentRun to verify")
    args = parser.parse_args()

    try:
        receipt = asyncio.run(build_receipt(args.run_id))
    except Exception as exc:
        print(json.dumps({
            "receipt_version": RECEIPT_VERSION,
            "overall": "ERROR",
            "error": str(exc),
        }, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
