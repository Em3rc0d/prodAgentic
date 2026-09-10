from __future__ import annotations

from domain.tenants.models import TenantContext


class MongoApprovalCalendarReader:
    """Safe Calendar projection over immutable ApprovalBundleV2 metadata."""

    def __init__(self, db, context: TenantContext):
        self.collection = db["approval_bundles"]
        self.context = context

    async def list_recent(self, *, limit: int = 100) -> list[dict]:
        cursor = (
            self.collection.find(
                {"tenant_id": self.context.tenant_id},
                {
                    "_id": 0,
                    "approval_id": 1,
                    "content_id": 1,
                    "revision_id": 1,
                    "approved_at": 1,
                    "assets": 1,
                    "bundle_sha256": 1,
                },
            )
            .sort([("approved_at", -1), ("approval_id", 1)])
            .limit(max(1, min(limit, 500)))
        )
        values = []
        async for raw in cursor:
            values.append(
                {
                    "approval_id": raw["approval_id"],
                    "content_id": raw["content_id"],
                    "revision_id": raw["revision_id"],
                    "approved_at": raw["approved_at"],
                    "bundle_sha256": raw["bundle_sha256"],
                    "asset_count": len(raw.get("assets") or []),
                }
            )
        return values
