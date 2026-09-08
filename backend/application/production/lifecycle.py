from __future__ import annotations

from datetime import datetime

from domain.planning.models import ContentEditorialState, utc_now
from domain.planning.ports import PlanningRepositoryPort


class ContentProductionConflict(RuntimeError):
    pass


class ContentProductionLifecycle:
    """Own ContentItem transitions for S3 without giving agents state authority."""

    def __init__(self, repository: PlanningRepositoryPort):
        self.repository = repository

    async def begin(self, content_id: str, *, now: datetime | None = None) -> None:
        clock = now or utc_now()
        changed = await self.repository.transition_content_item(
            content_id,
            expected_state=ContentEditorialState.PLANNED,
            new_state=ContentEditorialState.PRODUCING,
            now=clock,
        )
        if not changed:
            raise ContentProductionConflict(
                "ContentItem must be PLANNED before a new S3 production run can begin"
            )

    async def bind_text_revision(
        self,
        content_id: str,
        revision_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        clock = now or utc_now()
        changed = await self.repository.transition_content_item(
            content_id,
            expected_state=ContentEditorialState.PRODUCING,
            new_state=ContentEditorialState.PRODUCING,
            current_revision_id=revision_id,
            now=clock,
        )
        if not changed:
            raise ContentProductionConflict(
                "ContentItem production state changed before the S3 revision could be bound"
            )

    async def fail(self, content_id: str, *, now: datetime | None = None) -> bool:
        clock = now or utc_now()
        return await self.repository.transition_content_item(
            content_id,
            expected_state=ContentEditorialState.PRODUCING,
            new_state=ContentEditorialState.FAILED,
            now=clock,
        )
