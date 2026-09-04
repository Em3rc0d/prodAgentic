from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TenantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class Tenant(BaseModel):
    """The MK1 data-isolation root."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    status: TenantStatus = TenantStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Server-derived authority passed into every MK1 repository operation."""

    tenant_id: str
    actor_id: str
    actor_type: str = "operator"

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id cannot be blank")
        if not self.actor_id.strip():
            raise ValueError("actor_id cannot be blank")
        if self.actor_type not in {"operator", "worker", "service"}:
            raise ValueError("actor_type must be operator, worker, or service")
