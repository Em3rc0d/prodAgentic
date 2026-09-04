from collections.abc import Mapping
from typing import Any

from domain.tenants.models import TenantContext


class TenantScopeViolation(ValueError):
    pass


class TenantScopedMongoRepository:
    """Small S0 base adapter that makes tenant scope structurally required.

    New MK1 repositories compose this adapter instead of querying a business
    collection directly. Migration/admin tooling is deliberately separate.
    """

    def __init__(self, db: Any, collection_name: str, context: TenantContext):
        if not collection_name or collection_name.startswith("system."):
            raise ValueError("A valid business collection name is required")
        self.collection = db[collection_name]
        self.context = context

    def _scope(self, criteria: Mapping[str, Any] | None = None) -> dict[str, Any]:
        query = dict(criteria or {})
        requested_tenant = query.pop("tenant_id", self.context.tenant_id)
        if requested_tenant != self.context.tenant_id:
            raise TenantScopeViolation("Cross-tenant query rejected")
        return {"tenant_id": self.context.tenant_id, **query}

    async def find_one(self, criteria: Mapping[str, Any]) -> dict[str, Any] | None:
        return await self.collection.find_one(self._scope(criteria))

    async def insert_one(self, document: Mapping[str, Any]):
        payload = dict(document)
        requested_tenant = payload.pop("tenant_id", self.context.tenant_id)
        if requested_tenant != self.context.tenant_id:
            raise TenantScopeViolation("Cross-tenant write rejected")
        payload["tenant_id"] = self.context.tenant_id
        return await self.collection.insert_one(payload)

    async def update_one(self, criteria: Mapping[str, Any], update: Mapping[str, Any]):
        update_document = dict(update)
        if not update_document or any(not operator.startswith("$") for operator in update_document):
            raise TenantScopeViolation("Replacement updates are not allowed through a scoped repository")
        for operator, values in update_document.items():
            if not isinstance(values, Mapping):
                continue
            for field, value in values.items():
                if field == "tenant_id" or field.startswith("tenant_id."):
                    raise TenantScopeViolation("tenant_id is immutable across tenant scope")
                if (
                    operator == "$rename"
                    and isinstance(value, str)
                    and (value == "tenant_id" or value.startswith("tenant_id."))
                ):
                    raise TenantScopeViolation("tenant_id is immutable across tenant scope")
        return await self.collection.update_one(self._scope(criteria), update_document)
