from typing import Protocol

from domain.tenants.models import Tenant, TenantContext


class TenantRepositoryPort(Protocol):
    async def get_current(self, context: TenantContext) -> Tenant | None: ...

    async def ensure_bootstrap(self, tenant: Tenant) -> Tenant: ...
