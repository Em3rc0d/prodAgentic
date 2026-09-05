from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from domain.planning.models import FrozenModel, IdeaCandidateV1, NoveltyResultV1


class CandidateEvaluationV1(FrozenModel):
    candidate: IdeaCandidateV1
    novelty: NoveltyResultV1
    selected: bool
    selection_reason: str = Field(min_length=1, max_length=400)


class BatchPlanningTraceV1(FrozenModel):
    schema_version: Literal[1] = 1
    trace_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    memory_ids: tuple[str, ...] = ()
    evaluations: tuple[CandidateEvaluationV1, ...]
    created_at: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
