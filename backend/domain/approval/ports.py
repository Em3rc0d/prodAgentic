from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain.approval.models import ApprovalBundleV2, ApprovalReservationV1


class ApprovalRepositoryPort(Protocol):
    async def get_bundle(self, tenant_id: str, approval_id: str) -> ApprovalBundleV2 | None: ...

    async def get_by_revision(self, tenant_id: str, revision_id: str) -> ApprovalBundleV2 | None: ...

    async def reserve(
        self,
        *,
        tenant_id: str,
        content_id: str,
        revision_id: str,
        review_digest: str,
        approved_by: str,
        approved_at: datetime,
    ) -> ApprovalReservationV1: ...

    async def save_bundle(self, bundle: ApprovalBundleV2) -> None: ...

    async def ensure_ready_for_review(self, *, content_id: str, revision_id: str, now: datetime) -> bool: ...

    async def bind_approval(self, *, content_id: str, revision_id: str, approval_id: str, now: datetime) -> bool: ...
