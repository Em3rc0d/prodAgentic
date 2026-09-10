from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import MetricSnapshotV1


class MetricSnapshotRepositoryPort(Protocol):
    async def append(self, snapshot: MetricSnapshotV1) -> MetricSnapshotV1: ...

    async def get(self, metric_snapshot_id: str) -> MetricSnapshotV1 | None: ...

    async def get_by_operation_key(self, operation_key: str) -> MetricSnapshotV1 | None: ...

    async def list_for_publication(
        self,
        publication_id: str,
        *,
        limit: int = 100,
    ) -> list[MetricSnapshotV1]: ...

    async def list_recent(self, *, limit: int = 1000) -> list[MetricSnapshotV1]: ...

    async def latest_captured_at(self) -> datetime | None: ...
