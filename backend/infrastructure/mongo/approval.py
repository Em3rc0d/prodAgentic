from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from domain.approval.models import (
    ApprovalBundleV2,
    ApprovalReservationV1,
    canonical_approval_sha256,
)
from domain.planning.models import ContentEditorialState
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


def _hydrate_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return {key: _hydrate_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_hydrate_utc(item) for item in value]
    return value


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    value.pop("metadata_digest", None)
    return _hydrate_utc(value)


class MongoApprovalRepository:
    """S7 immutable approval authority plus a restart-safe reservation boundary."""

    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.approvals = TenantScopedMongoRepository(db, "approval_bundles", context)
        self.reservations = TenantScopedMongoRepository(db, "approval_reservations", context)
        self.items = TenantScopedMongoRepository(db, "content_items", context)

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.context.tenant_id:
            raise ValueError("Approval repository tenant authority mismatch")

    async def get_bundle(self, tenant_id: str, approval_id: str) -> ApprovalBundleV2 | None:
        self._require_tenant(tenant_id)
        raw = await self.approvals.find_one({"approval_id": approval_id})
        if raw is None:
            return None
        metadata_digest = raw.get("metadata_digest")
        bundle = ApprovalBundleV2.model_validate(_clean(raw))
        if metadata_digest != bundle.bundle_sha256:
            raise ValueError("persisted ApprovalBundleV2 metadata digest mismatch")
        return bundle

    async def get_by_revision(self, tenant_id: str, revision_id: str) -> ApprovalBundleV2 | None:
        self._require_tenant(tenant_id)
        raw = await self.approvals.find_one({"revision_id": revision_id})
        if raw is None:
            return None
        metadata_digest = raw.get("metadata_digest")
        bundle = ApprovalBundleV2.model_validate(_clean(raw))
        if metadata_digest != bundle.bundle_sha256:
            raise ValueError("persisted ApprovalBundleV2 metadata digest mismatch")
        return bundle

    async def reserve(
        self,
        *,
        tenant_id: str,
        content_id: str,
        revision_id: str,
        review_digest: str,
        approved_by: str,
        approved_at: datetime,
    ) -> ApprovalReservationV1:
        self._require_tenant(tenant_id)
        approval_id = "approval-" + hashlib.sha256(
            f"{tenant_id}|{content_id}|{revision_id}|{review_digest}|{approved_by}".encode("utf-8")
        ).hexdigest()[:40]
        candidate = ApprovalReservationV1(
            approval_id=approval_id,
            tenant_id=tenant_id,
            content_id=content_id,
            revision_id=revision_id,
            review_digest=review_digest,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        try:
            await self.reservations.insert_one(candidate.model_dump(mode="json"))
            return candidate
        except DuplicateKeyError:
            raw = await self.reservations.find_one({"revision_id": revision_id})
            if raw is None:
                raise
            existing = ApprovalReservationV1.model_validate(_clean(raw))
            if existing.review_digest != review_digest or existing.approved_by != approved_by:
                raise ValueError("revision approval is already reserved by another review intent")
            return existing

    async def save_bundle(self, bundle: ApprovalBundleV2) -> None:
        self._require_tenant(bundle.tenant_id)
        existing = await self.get_by_revision(bundle.tenant_id, bundle.revision_id)
        if existing is not None:
            if existing != bundle:
                raise ValueError("immutable ApprovalBundleV2 identity collision")
            return
        # Preserve the exact signed approval timestamp across Mongo round trips.
        payload = bundle.model_dump(mode="json")
        payload["metadata_digest"] = bundle.bundle_sha256
        try:
            await self.approvals.insert_one(payload)
        except DuplicateKeyError:
            existing = await self.get_by_revision(bundle.tenant_id, bundle.revision_id)
            if existing != bundle:
                raise ValueError("immutable ApprovalBundleV2 identity collision")

    async def ensure_ready_for_review(self, *, content_id: str, revision_id: str, now: datetime) -> bool:
        # S6 owns Revision.REVIEWABLE; S7 only mirrors that already-proven authority into
        # the ContentItem editorial lifecycle before the explicit human approval boundary.
        result = await self.items.update_one(
            {
                "content_id": content_id,
                "current_revision_id": revision_id,
                "editorial_state": ContentEditorialState.PRODUCING.value,
            },
            {"$set": {"editorial_state": ContentEditorialState.READY_FOR_REVIEW.value, "updated_at": now}},
        )
        if result.matched_count == 1:
            return True
        raw = await self.items.find_one({"content_id": content_id, "current_revision_id": revision_id})
        return raw is not None and raw.get("editorial_state") in {
            ContentEditorialState.READY_FOR_REVIEW.value,
            ContentEditorialState.APPROVED.value,
        }

    async def bind_approval(self, *, content_id: str, revision_id: str, approval_id: str, now: datetime) -> bool:
        bundle = await self.get_bundle(self.context.tenant_id, approval_id)
        if bundle is None or bundle.content_id != content_id or bundle.revision_id != revision_id:
            raise ValueError("ApprovalBundleV2 must be durable before ContentItem approval CAS")

        result = await self.items.update_one(
            {
                "content_id": content_id,
                "current_revision_id": revision_id,
                "editorial_state": ContentEditorialState.READY_FOR_REVIEW.value,
                "latest_approval_id": None,
            },
            {
                "$set": {
                    "editorial_state": ContentEditorialState.APPROVED.value,
                    "latest_approval_id": approval_id,
                    "updated_at": now,
                }
            },
        )
        if result.matched_count == 1:
            return True
        raw = await self.items.find_one({"content_id": content_id, "current_revision_id": revision_id})
        return bool(
            raw
            and raw.get("editorial_state") == ContentEditorialState.APPROVED.value
            and raw.get("latest_approval_id") == approval_id
        )
