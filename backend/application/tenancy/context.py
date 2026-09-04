import os
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException, Request

from domain.tenants.models import TenantContext


def bootstrap_tenant_id() -> str:
    """Resolve one stable tenant ID for the current single-admin installation.

    An explicit UUID supports an installation that already assigned an ID. The
    deterministic fallback is stable across restarts and is never client input.
    """

    configured = os.environ.get("PRODAGENTIC_BOOTSTRAP_TENANT_ID", "").strip()
    if configured:
        try:
            return str(UUID(configured))
        except ValueError as exc:
            raise ValueError("PRODAGENTIC_BOOTSTRAP_TENANT_ID must be a UUID") from exc

    deployment_key = os.environ.get("PRODAGENTIC_DEPLOYMENT_KEY", "default-installation").strip()
    if not deployment_key:
        raise ValueError("PRODAGENTIC_DEPLOYMENT_KEY cannot be blank")
    return str(uuid5(NAMESPACE_URL, f"prodagentic:mk1:tenant:{deployment_key}"))


def tenant_context_for_actor(actor_id: str, actor_type: str = "operator") -> TenantContext:
    """Create authority from trusted server identity, never request parameters."""

    return TenantContext(
        tenant_id=bootstrap_tenant_id(),
        actor_id=actor_id,
        actor_type=actor_type,
    )


def require_tenant_context(request: Request) -> TenantContext:
    context = getattr(request.state, "tenant_context", None)
    if not isinstance(context, TenantContext):
        raise HTTPException(status_code=401, detail="Tenant context is unavailable")
    return context
