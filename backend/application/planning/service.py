from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from application.planning.novelty import NoveltyEngine
from domain.planning.models import (
    Batch,
    BatchRequestConstraints,
    BatchState,
    BatchSummaryCounts,
    ContentItem,
    ContentPlanV1,
    NoveltyResultV1,
    NoveltyVerdict,
    PersistedContentPlan,
    PlannerStrategySnapshot,
    TargetWindow,
    canonical_sha256,
    canonicalize_topic,
    utc_now,
)
from domain.planning.ports import CandidateSourcePort, MemoryProjectorPort, PlanningRepositoryPort
from domain.planning.trace import BatchPlanningTraceV1, CandidateEvaluationV1
from domain.profiles.ports import ProfileRepositoryPort


class PlanningConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannedBatchResult:
    batch: Batch
    items: tuple[ContentItem, ...]
    plans: tuple[PersistedContentPlan, ...]
    trace: BatchPlanningTraceV1
    memory_count: int


class BatchPlannerService:
    memory_window_days = 30
    candidate_cap = 24

    def __init__(
        self,
        profile_repository: ProfileRepositoryPort,
        planning_repository: PlanningRepositoryPort,
        candidate_source: CandidateSourcePort,
        memory_projector: MemoryProjectorPort,
        novelty_engine: NoveltyEngine | None = None,
    ):
        self.profile_repository = profile_repository
        self.planning_repository = planning_repository
        self.candidate_source = candidate_source
        self.memory_projector = memory_projector
        self.novelty_engine = novelty_engine or NoveltyEngine()

    async def create_batch(
        self,
        tenant_id: str,
        profile_id: str,
        target_window: TargetWindow,
        requested_size: int,
        constraints: BatchRequestConstraints,
        *,
        now: datetime | None = None,
    ) -> PlannedBatchResult:
        if requested_size < 1 or requested_size > 30:
            raise ValueError("requested_size must be between 1 and 30")

        clock = now or utc_now()
        profile = await self.profile_repository.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        if profile.tenant_id != tenant_id:
            raise LookupError("Profile not found")

        profile_version = await self.profile_repository.get_version(profile_id, profile.current_version)
        if profile_version is None:
            raise PlanningConflict("Current ProfileVersion is unavailable")
        if profile_version.tenant_id != tenant_id:
            raise PlanningConflict("ProfileVersion tenant authority mismatch")

        # Memory refresh is required. A failure propagates rather than silently
        # planning with an empty/stateless memory set.
        await self.memory_projector.refresh(profile_id, clock)
        memory_since = clock - timedelta(days=self.memory_window_days)
        memory = await self.planning_repository.list_recent_memory(profile_id, memory_since)

        target_pool_size = min(self.candidate_cap, max(8, requested_size * 3))
        candidates = self.candidate_source.generate(
            profile_version,
            target_window,
            constraints,
            target_pool_size,
        )
        if len(candidates) > self.candidate_cap:
            candidates = candidates[: self.candidate_cap]
        candidate_ids = [item.candidate_id for item in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise PlanningConflict("Candidate source returned duplicate candidate IDs")

        selected = []
        selected_results: dict[str, NoveltyResultV1] = {}
        remaining = list(candidates)

        while remaining and len(selected) < requested_size:
            ranked: list[tuple[tuple[int, ...], object, NoveltyResultV1]] = []
            selected_roles = {item.role for item in selected}
            selected_topics = {canonicalize_topic(item.topic) for item in selected}
            selected_hooks = {item.hook_pattern for item in selected}
            selected_formats = {item.tentative_format for item in selected}

            for candidate in remaining:
                result = self.novelty_engine.evaluate(candidate, memory, selected, clock)
                if result.verdict not in (NoveltyVerdict.PASS, NoveltyVerdict.PASS_WITH_WARNING):
                    continue
                diversity = (
                    int(candidate.role not in selected_roles),
                    int(canonicalize_topic(candidate.topic) not in selected_topics),
                    int(candidate.hook_pattern not in selected_hooks),
                    int(candidate.tentative_format not in selected_formats),
                    int(result.verdict == NoveltyVerdict.PASS),
                    int(candidate.claim_risk.value == "low"),
                )
                ranked.append((diversity, candidate, result))

            if not ranked:
                break
            ranked.sort(key=lambda value: value[0], reverse=True)
            _, chosen, chosen_result = ranked[0]
            selected.append(chosen)
            selected_results[chosen.candidate_id] = chosen_result
            remaining = [item for item in remaining if item.candidate_id != chosen.candidate_id]

        # Re-evaluate all unselected candidates against the final selected set so
        # the persisted trace explains why they did not become ContentItems.
        evaluations: list[CandidateEvaluationV1] = []
        for candidate in candidates:
            if candidate.candidate_id in selected_results:
                result = selected_results[candidate.candidate_id]
                reason = "selected after hard novelty gates and diversity preference"
                is_selected = True
            else:
                result = self.novelty_engine.evaluate(candidate, memory, selected, clock)
                is_selected = False
                if len(selected) >= requested_size and result.verdict in (
                    NoveltyVerdict.PASS,
                    NoveltyVerdict.PASS_WITH_WARNING,
                ):
                    reason = "fresh candidate not needed after requested batch size was satisfied"
                else:
                    reason = f"not selected because novelty verdict was {result.verdict.value}"
            evaluations.append(
                CandidateEvaluationV1(
                    candidate=candidate,
                    novelty=result,
                    selected=is_selected,
                    selection_reason=reason,
                )
            )

        batch_id = str(uuid4())
        items: list[ContentItem] = []
        plans: list[PersistedContentPlan] = []
        for candidate in selected:
            novelty = selected_results[candidate.candidate_id]
            content_id = str(uuid4())
            plan_id = str(uuid4())
            visual_hint = {
                "single_image": "single_focus",
                "carousel": "sequence",
                "infographic": "structured_diagram",
            }.get(candidate.tentative_format)
            rationale = candidate.rationale
            if novelty.verdict == NoveltyVerdict.PASS_WITH_WARNING and novelty.reasons:
                rationale = f"{rationale}; novelty warning retained: {novelty.reasons[0]}"
            plan = ContentPlanV1(
                plan_id=plan_id,
                candidate_id=candidate.candidate_id,
                profile_id=profile_id,
                profile_version=profile_version.version,
                role=candidate.role,
                canonical_topic=novelty.canonical_topic,
                subtopics=candidate.subtopics,
                angle=candidate.angle,
                target_effect=candidate.target_effect,
                format=candidate.tentative_format,
                hook_pattern=candidate.hook_pattern,
                visual_pattern_hint=visual_hint,
                novelty_result_ref=novelty.novelty_result_id,
                planning_rationale=rationale,
            )
            items.append(
                ContentItem(
                    content_id=content_id,
                    tenant_id=tenant_id,
                    batch_id=batch_id,
                    profile_id=profile_id,
                    profile_version=profile_version.version,
                    canonical_topic=novelty.canonical_topic,
                    subtopics=candidate.subtopics,
                    angle=candidate.angle,
                    role=candidate.role,
                    target_effect=candidate.target_effect,
                    format=candidate.tentative_format,
                    hook_pattern=candidate.hook_pattern,
                    visual_pattern=visual_hint,
                    created_at=clock,
                    updated_at=clock,
                )
            )
            plans.append(
                PersistedContentPlan(
                    artifact_id=plan_id,
                    tenant_id=tenant_id,
                    batch_id=batch_id,
                    content_id=content_id,
                    plan=plan,
                    digest=canonical_sha256(plan),
                    created_at=clock,
                )
            )

        final_by_id = {item.candidate.candidate_id: item.novelty for item in evaluations}
        blocked = sum(
            1
            for result in final_by_id.values()
            if result.verdict in (NoveltyVerdict.BLOCKED, NoveltyVerdict.REPLACE_TOPIC)
        )
        rewrites = sum(1 for result in final_by_id.values() if result.verdict == NoveltyVerdict.REWRITE_ANGLE)
        warnings = sum(1 for result in final_by_id.values() if result.verdict == NoveltyVerdict.PASS_WITH_WARNING)
        selected_size = len(items)
        state = BatchState.PLANNED if selected_size == requested_size else BatchState.PARTIAL
        shortfall = None
        if selected_size < requested_size:
            shortfall = (
                f"Selected {selected_size} of {requested_size}; hard novelty/diversity gates "
                "were not relaxed to fill the batch."
            )
        strategy = PlannerStrategySnapshot(
            memory_window_days=self.memory_window_days,
            memory_cutoff_at=clock,
            candidate_pool_size=len(candidates),
        )
        summary = BatchSummaryCounts(
            candidates_generated=len(candidates),
            candidates_blocked=blocked,
            candidates_rewrite=rewrites,
            candidates_warning=warnings,
            selected=selected_size,
        )
        batch = Batch(
            batch_id=batch_id,
            tenant_id=tenant_id,
            profile_id=profile_id,
            profile_version=profile_version.version,
            profile_snapshot_digest=profile_version.digest,
            target_window=target_window,
            requested_size=requested_size,
            selected_size=selected_size,
            request_constraints=constraints,
            strategy_snapshot=strategy,
            state=state,
            summary_counts=summary,
            shortfall_reason=shortfall,
            created_at=clock,
            updated_at=clock,
        )

        trace_payload = {
            "schema_version": 1,
            "trace_id": f"trace-{batch_id}",
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "profile_id": profile_id,
            "profile_version": profile_version.version,
            "memory_ids": [item.memory_id for item in memory],
            "evaluations": [item.model_dump(mode="json") for item in evaluations],
            "created_at": clock.isoformat(),
        }
        trace = BatchPlanningTraceV1(**trace_payload, digest=canonical_sha256(trace_payload))
        await self.planning_repository.save_batch(batch, items, plans, trace)
        return PlannedBatchResult(
            batch=batch,
            items=tuple(items),
            plans=tuple(plans),
            trace=trace,
            memory_count=len(memory),
        )
