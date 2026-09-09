from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from db.mongo import _ensure_mk1_approval_indexes, _ensure_mk1_planning_indexes
from domain.approval.models import ApprovalAssetV2, ApprovalBundleV2, canonical_approval_sha256
from domain.planning.models import ContentEditorialState, ContentItem
from domain.tenants.models import TenantContext
from infrastructure.mongo.approval import MongoApprovalRepository
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


NOW = datetime(2026, 9, 9, 11, 0, tzinfo=timezone.utc)


def make_item():
    return ContentItem(
        content_id="content-s7-mongo", tenant_id="tenant-s7-a", batch_id="batch-s7",
        profile_id="profile-s7", profile_version=1, canonical_topic="s7", angle="approval",
        role="educate", target_effect="trust", format="single_image", hook_pattern="question",
        editorial_state=ContentEditorialState.PRODUCING, current_revision_id="revision-s7-mongo",
        created_at=NOW, updated_at=NOW,
    )


def make_bundle(approval_id: str):
    payload = {
        "schema_version": 2,
        "approval_id": approval_id,
        "tenant_id": "tenant-s7-a",
        "content_id": "content-s7-mongo",
        "revision_id": "revision-s7-mongo",
        "profile_snapshot_digest": "a" * 64,
        "plan_digest": "b" * 64,
        "research_digest": "c" * 64,
        "content_digest": "d" * 64,
        "visual_spec_digest": "e" * 64,
        "assets": [ApprovalAssetV2(asset_id="asset-s7", sha256="f" * 64)],
        "qa_digest": "1" * 64,
        "policy_version": "qa-policy-v1",
        "approved_by": "operator-s7",
        "approved_at": NOW,
    }
    return ApprovalBundleV2(**payload, bundle_sha256=canonical_approval_sha256(payload))


@pytest.mark.asyncio
async def test_real_mongodb_s7_reservation_restart_and_immutable_approval_cas():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S7 approval gate")

    database_name = f"prodagentic_s7_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_planning_indexes(db)
        await _ensure_mk1_approval_indexes(db)
        context = TenantContext(tenant_id="tenant-s7-a", actor_id="operator-s7")
        items = TenantScopedMongoRepository(db, "content_items", context)
        await items.insert_one(make_item().model_dump())

        repository = MongoApprovalRepository(db, context)
        reservation = await repository.reserve(
            tenant_id=context.tenant_id, content_id="content-s7-mongo", revision_id="revision-s7-mongo",
            review_digest="2" * 64, approved_by=context.actor_id, approved_at=NOW,
        )
        assert reservation.approval_id.startswith("approval-")

        # Process restart: the same review intent must reopen the durable reservation.
        reopened = MongoApprovalRepository(db, context)
        replay = await reopened.reserve(
            tenant_id=context.tenant_id, content_id="content-s7-mongo", revision_id="revision-s7-mongo",
            review_digest="2" * 64, approved_by=context.actor_id,
            approved_at=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
        )
        assert replay == reservation

        with pytest.raises(ValueError, match="another review intent"):
            await reopened.reserve(
                tenant_id=context.tenant_id, content_id="content-s7-mongo", revision_id="revision-s7-mongo",
                review_digest="3" * 64, approved_by="other-operator", approved_at=NOW,
            )

        assert await reopened.ensure_ready_for_review(
            content_id="content-s7-mongo", revision_id="revision-s7-mongo", now=NOW
        )
        bundle = make_bundle(reservation.approval_id)
        await reopened.save_bundle(bundle)
        assert await reopened.get_by_revision(context.tenant_id, "revision-s7-mongo") == bundle
        assert await reopened.save_bundle(bundle) is None
        assert await reopened.bind_approval(
            content_id="content-s7-mongo", revision_id="revision-s7-mongo",
            approval_id=bundle.approval_id, now=NOW,
        )
        # Idempotent replay after crash/restart.
        assert await MongoApprovalRepository(db, context).bind_approval(
            content_id="content-s7-mongo", revision_id="revision-s7-mongo",
            approval_id=bundle.approval_id, now=NOW,
        )
        persisted = await items.find_one({"content_id": "content-s7-mongo"})
        assert persisted["editorial_state"] == ContentEditorialState.APPROVED.value
        assert persisted["latest_approval_id"] == bundle.approval_id

        other = MongoApprovalRepository(db, TenantContext(tenant_id="tenant-s7-b", actor_id="operator-s7-b"))
        assert await other.get_by_revision("tenant-s7-b", "revision-s7-mongo") is None
    finally:
        await client.drop_database(database_name)
        client.close()
