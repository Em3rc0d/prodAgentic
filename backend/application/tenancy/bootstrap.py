from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from application.tenancy.context import bootstrap_tenant_id
from domain.tenants.models import Tenant
from infrastructure.mongo.tenants import MongoTenantRepository


LEGACY_BUSINESS_COLLECTIONS = (
    "content_profiles",
    "content_runs",
    "posts",
    "linkedin_connections",
)


@dataclass(frozen=True)
class BootstrapMigrationReport:
    migration: str
    tenant_id: str
    matched_by_collection: dict[str, int]
    modified_by_collection: dict[str, int]
    missing_after_migration: dict[str, int]
    invalid_after_migration: dict[str, int]
    completed_at: datetime

    @property
    def verified(self) -> bool:
        return (
            all(count == 0 for count in self.missing_after_migration.values())
            and all(count == 0 for count in self.invalid_after_migration.values())
        )


async def migrate_bootstrap_tenant(db: Any) -> BootstrapMigrationReport:
    """Idempotently map the current MK0 single-admin records to one tenant.

    This only adds isolation metadata; it does not reinterpret MK0 records as
    typed MK1 entities or transfer write authority. Existing non-empty tenant
    assignments are preserved. Explicit null/blank assignments are not silently
    overwritten; verification reports them as invalid so the migration fails
    closed and requires operator review.
    """

    tenant_id = bootstrap_tenant_id()
    tenant = Tenant(tenant_id=tenant_id, name="Bootstrap tenant")
    await MongoTenantRepository(db).ensure_bootstrap(tenant)

    matched: dict[str, int] = {}
    modified: dict[str, int] = {}
    missing: dict[str, int] = {}
    invalid: dict[str, int] = {}
    for collection_name in LEGACY_BUSINESS_COLLECTIONS:
        collection = db[collection_name]
        result = await collection.update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": tenant_id}},
        )
        matched[collection_name] = int(result.matched_count)
        modified[collection_name] = int(result.modified_count)
        missing[collection_name] = int(
            await collection.count_documents({"tenant_id": {"$exists": False}})
        )
        invalid[collection_name] = int(
            await collection.count_documents(
                {"tenant_id": {"$exists": True, "$in": [None, ""]}}
            )
        )

    return BootstrapMigrationReport(
        migration="mk1_s0_bootstrap_tenant_v1",
        tenant_id=tenant_id,
        matched_by_collection=matched,
        modified_by_collection=modified,
        missing_after_migration=missing,
        invalid_after_migration=invalid,
        completed_at=datetime.now(timezone.utc),
    )


async def verify_bootstrap_tenant(db: Any) -> BootstrapMigrationReport:
    """Verification is intentionally the same idempotent operation as forward."""

    return await migrate_bootstrap_tenant(db)
