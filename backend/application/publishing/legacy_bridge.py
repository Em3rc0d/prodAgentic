from __future__ import annotations

from dataclasses import dataclass

from application.tenancy.context import bootstrap_tenant_id
from domain.tenants.models import TenantContext
from infrastructure.mongo.publishing import MongoConnectionRepository


@dataclass(frozen=True)
class LinkedInConnectionMigrationReport:
    tenant_id: str
    found_legacy: bool
    migrated: bool
    connection_id: str | None


async def migrate_legacy_linkedin_connection(db) -> LinkedInConnectionMigrationReport:
    """Idempotently migrate the MK0 singleton OAuth connection to bootstrap S10 authority."""
    tenant_id = bootstrap_tenant_id()
    legacy = await db["linkedin_connections"].find_one({"_id": "primary"})
    if not legacy:
        return LinkedInConnectionMigrationReport(
            tenant_id=tenant_id,
            found_legacy=False,
            migrated=False,
            connection_id=None,
        )
    context = TenantContext(tenant_id=tenant_id, actor_id="mk1-s10-migration", actor_type="service")
    repo = MongoConnectionRepository(db, context)
    connection = await repo.import_legacy_linkedin(legacy, allow_bootstrap=True)
    return LinkedInConnectionMigrationReport(
        tenant_id=tenant_id,
        found_legacy=True,
        migrated=True,
        connection_id=connection.get("connection_id"),
    )
