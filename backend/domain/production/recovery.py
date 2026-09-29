from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field, model_validator

from domain.planning.models import ContentItem, PersistedContentPlan, NoveltyResultV1
from domain.production.models import FrozenModel, GenerationFailureV1, canonical_sha256
from domain.production.failures import ProductionRecoveryAction


class RecoveryDecisionV1(FrozenModel):
    schema_version: Literal[1] = 1
    content_id: str
    run_id: str | None = None
    action: ProductionRecoveryAction
    code: str
    stage: str
    retryable: bool = False
    safe_message: str
    replacement_content_id: str | None = None


class ReplacementPlanV1(FrozenModel):
    schema_version: Literal[1] = 1
    recovery_id: str
    tenant_id: str
    batch_id: str
    rejected_content_id: str
    rejected_plan_id: str
    rejected_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_run_id: str
    failure: GenerationFailureV1
    profile_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    planning_trace_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    memory_ids: tuple[str, ...]
    novelty: NoveltyResultV1
    replacement_item: ContentItem
    replacement_plan: PersistedContentPlan
    created_at: datetime

    @model_validator(mode="after")
    def bind_predecessors(self):
        item, persisted = self.replacement_item, self.replacement_plan
        plan = persisted.plan
        if (item.tenant_id != self.tenant_id or persisted.tenant_id != self.tenant_id
                or item.batch_id != self.batch_id or persisted.batch_id != self.batch_id
                or persisted.content_id != item.content_id or persisted.artifact_id != plan.plan_id
                or persisted.digest != canonical_sha256(plan)
                or plan.profile_id != item.profile_id or plan.profile_version != item.profile_version
                or self.rejected_content_id == item.content_id or self.rejected_plan_id == plan.plan_id
                or self.failure.recovery_action != ProductionRecoveryAction.REPLAN_CONTENT
                or self.novelty.candidate_id != plan.candidate_id
                or self.novelty.novelty_result_id != plan.novelty_result_ref
                or self.novelty.verdict.value not in {"PASS", "PASS_WITH_WARNING"}):
            raise ValueError("Replacement authority is inconsistent")
        for field in ("role", "canonical_topic", "subtopics", "angle", "target_effect", "format", "hook_pattern"):
            if getattr(plan, field) != getattr(item, field):
                raise ValueError("Replacement plan/item fields differ")
        return self


class RecoveryConflict(RuntimeError):
    pass


class RecoveryRepositoryPort(Protocol):
    async def read(self, batch_id: str) -> tuple[int, list[ReplacementPlanV1]]: ...
    async def append(self, version: int, value: ReplacementPlanV1) -> bool: ...
    async def materialize(self, planning, entry: ReplacementPlanV1) -> ContentItem: ...
