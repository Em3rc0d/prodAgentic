from typing import Any

from domain.tenants.models import Tenant, TenantContext


class MongoTenantRepository:
    def __init__(self, db: Any):
        self.collection = db["tenants"]

    async def get_current(self, context: TenantContext) -> Tenant | None:
        document = await self.collection.find_one({"tenant_id": context.tenant_id})
        if document is None:
            return None
        document.pop("_id", None)
        return Tenant.model_validate(document)

    async def ensure_bootstrap(self, tenant: Tenant) -> Tenant:
        await self.collection.update_one(
            {"tenant_id": tenant.tenant_id},
            {"$setOnInsert": tenant.model_dump()},
            upsert=True,
        )
        document = await self.collection.find_one({"tenant_id": tenant.tenant_id})
        if document is None:
            raise RuntimeError("Bootstrap tenant upsert did not produce a tenant")
        document.pop("_id", None)
        return Tenant.model_validate(document)
