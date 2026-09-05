from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain.planning.models import (
    Batch,
    BatchRequestConstraints,
    ContentItem,
    EditorialMemoryEntry,
    IdeaCandidateV1,
    PersistedContentPlan,
    TargetWindow,
)
from domain.planning.trace import BatchPlanningTraceV1
from domain.profiles.models import ProfileVersion


class CandidateSourcePort(Protocol):
    def generate(
        self,
        profile: ProfileVersion,
        target_window: TargetWindow,
        constraints: BatchRequestConstraints,
        target_pool_size: int,
    ) -> list[IdeaCandidateV1]: ...


class MemoryProjectorPort(Protocol):
    async def refresh(self, profile_id: str, now: datetime) -> int: ...


class PlanningRepositoryPort(Protocol):
    async def list_recent_memory(
        self,
        profile_id: str,
        since: datetime,
    ) -> list[EditorialMemoryEntry]: ...

    async def replace_projected_memory(
        self,
        profile_id: str,
        entries: list[EditorialMemoryEntry],
        source_prefix: str,
    ) -> None: ...

    async def save_batch(
        self,
        batch: Batch,
        items: list[ContentItem],
        plans: list[PersistedContentPlan],
        trace: BatchPlanningTraceV1,
    ) -> None: ...

    async def get_batch(self, batch_id: str) -> Batch | None: ...

    async def list_batch_items(self, batch_id: str) -> list[ContentItem]: ...

    async def list_batch_plans(self, batch_id: str) -> list[PersistedContentPlan]: ...

    async def get_planning_trace(self, batch_id: str) -> BatchPlanningTraceV1 | None: ...
