from __future__ import annotations

from typing import Protocol

from .models import PerformanceEvidenceSetV1, PerformanceSummaryV1, PlannerPerformanceScoreV1


class PerformanceEvidenceRepositoryPort(Protocol):
    async def list_for_profile(self, profile_id: str) -> PerformanceEvidenceSetV1: ...


class PerformanceSummaryRepositoryPort(Protocol):
    async def append(self, summary: PerformanceSummaryV1) -> PerformanceSummaryV1: ...

    async def get_by_input_digest(self, profile_id: str, input_digest: str) -> PerformanceSummaryV1 | None: ...

    async def latest_for_profile(self, profile_id: str) -> PerformanceSummaryV1 | None: ...


class PlannerPerformanceSourcePort(Protocol):
    async def get_for_planning(self, profile_id: str) -> PerformanceSummaryV1 | None: ...

    def score_candidate(
        self,
        summary: PerformanceSummaryV1,
        *,
        role: str,
        canonical_topic: str,
        format: str,
        hook_pattern: str,
        visual_pattern: str | None,
    ) -> PlannerPerformanceScoreV1: ...
