from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from application.planning.novelty import NoveltyEngine
from application.planning.strict import batch_distinctness_issues
from domain.planning.models import ContentItem, ContentPlanV1, PersistedContentPlan, NoveltyVerdict, ContentEditorialState
from domain.production.models import GenerationRunState, canonical_sha256, utc_now
from domain.production.failures import ProductionRecoveryAction as Action
from domain.production.recovery import RecoveryDecisionV1, ReplacementPlanV1
from domain.production.recovery import RecoveryConflict, RecoveryRepositoryPort
from domain.planning.ports import PlanningRepositoryPort, MemoryProjectorPort
from domain.profiles.ports import ProfileRepositoryPort
from domain.profiles.models import canonical_digest as profile_digest
from domain.production.ports import ProductionRepositoryPort


def recovery_decision(item, run, replacement=None):
    if replacement is not None:
        return RecoveryDecisionV1(
            content_id=item.content_id, run_id=run.run_id if run else None,
            action=Action.NONE, code="IDEA_REPLACED", stage="planning",
            safe_message="This idea was replaced. Continue with its replacement.",
            replacement_content_id=replacement.replacement_item.content_id,
        )
    if item.editorial_state in {ContentEditorialState.FAILED, ContentEditorialState.PRODUCING} and run and run.state == GenerationRunState.FAILED and run.failure:
        return RecoveryDecisionV1(
            content_id=item.content_id, run_id=run.run_id,
            action=run.failure.recovery_action, code=run.failure.code,
            stage=run.failure.stage, retryable=run.failure.retryable,
            safe_message=run.failure.safe_message,
        )
    if item.current_revision_id and item.editorial_state in {
        ContentEditorialState.PRODUCING, ContentEditorialState.READY_FOR_REVIEW,
    } and run and run.state in {GenerationRunState.VISUAL_PLANNING, GenerationRunState.RENDERING, GenerationRunState.QA, GenerationRunState.COMPLETED}:
        return RecoveryDecisionV1(content_id=item.content_id, run_id=run.run_id,
                                  action=Action.RESUME_PIPELINE, code="PERSISTED_REVISION", stage="production",
                                  safe_message=run.failure.safe_message if run.failure else "Continue from the saved draft.",
                                  retryable=bool(run.failure and run.failure.retryable))
    return RecoveryDecisionV1(content_id=item.content_id, run_id=run.run_id if run else None,
                              action=Action.HUMAN_ACTION_REQUIRED if item.editorial_state == ContentEditorialState.FAILED else Action.NONE,
                              code="RECOVERY_UNAVAILABLE", stage="production",
                              safe_message="Review the current state before continuing.")


class ContentReplacementService:
    def __init__(self, planning: PlanningRepositoryPort, production: ProductionRepositoryPort,
                 profiles: ProfileRepositoryPort, recovery: RecoveryRepositoryPort, projector: MemoryProjectorPort):
        self.planning, self.production, self.profiles = planning, production, profiles
        self.recovery, self.projector = recovery, projector

    async def replace(self, *, tenant_id, content_id, expected_run_id):
        item = await self.planning.get_content_item(content_id)
        run = await self.production.latest_run(tenant_id, content_id)
        if item is None or item.tenant_id != tenant_id or run is None or run.run_id != expected_run_id:
            raise RecoveryConflict("Recovery snapshot changed; reload the item")
        if (item.editorial_state != ContentEditorialState.FAILED or run.state != GenerationRunState.FAILED
                or run.failure is None or run.failure.recovery_action != Action.REPLAN_CONTENT):
            raise RecoveryConflict("This failure does not authorize a replacement")
        rejected = await self.planning.get_plan_for_content(content_id)
        profile = await self.profiles.get_version(item.profile_id, item.profile_version)
        batch = await self.planning.get_batch(item.batch_id)
        trace = await self.planning.get_planning_trace(item.batch_id)
        if rejected is None or profile is None or batch is None or trace is None:
            raise RecoveryConflict("Frozen replacement predecessors are unavailable")
        if (rejected.plan.plan_id != run.plan_id or rejected.digest != run.plan_digest
                or canonical_sha256(rejected.plan) != run.plan_digest or profile.digest != run.profile_snapshot_digest
                or profile_digest(profile) != profile.digest
                or batch.profile_snapshot_digest != profile.digest or trace.profile_version != profile.version
                or trace.profile_id != profile.profile_id or trace.tenant_id != tenant_id
                or rejected.tenant_id != tenant_id or rejected.batch_id != item.batch_id):
            raise RecoveryConflict("Replacement predecessor authority mismatch")
        if canonical_sha256(trace.model_dump(mode="json", exclude={"digest"})) != trace.digest:
            raise RecoveryConflict("Planning trace digest mismatch; replacement requires intact candidate authority")
        for _ in range(4):
            version, entries = await self.recovery.read(item.batch_id)
            existing = next((entry for entry in entries if entry.rejected_content_id == content_id), None)
            if existing:
                await self.recovery.materialize(self.planning, existing)
                return existing
            now = utc_now()
            await self.projector.refresh(item.profile_id, now)
            memory = await self.planning.list_recent_memory(item.profile_id, now - timedelta(days=30))
            items = await self.planning.list_batch_items(item.batch_id)
            plans = await self.planning.list_batch_plans(item.batch_id)
            used = {plan.plan.candidate_id for plan in plans}
            used.update(entry.replacement_plan.plan.candidate_id for entry in entries)
            # Pending projections participate in collision checking too.
            by_id = {other.content_id: other for other in items}
            by_id.update({entry.replacement_item.content_id: entry.replacement_item for entry in entries})
            all_items = list(by_id.values())
            chosen = None
            for evaluation in trace.evaluations:
                candidate = evaluation.candidate
                if candidate.candidate_id in used:
                    continue
                novelty = NoveltyEngine().evaluate(candidate, memory,
                    [e.candidate for e in trace.evaluations if e.candidate.candidate_id in used], now)
                if novelty.verdict not in {NoveltyVerdict.PASS, NoveltyVerdict.PASS_WITH_WARNING}:
                    continue
                new_id = str(uuid4())
                candidate_item = ContentItem(
                    content_id=new_id, tenant_id=tenant_id, batch_id=item.batch_id,
                    profile_id=item.profile_id, profile_version=item.profile_version,
                    canonical_topic=novelty.canonical_topic, subtopics=candidate.subtopics,
                    angle=candidate.angle, role=candidate.role, target_effect=candidate.target_effect,
                    format=candidate.tentative_format, hook_pattern=candidate.hook_pattern,
                    created_at=now, updated_at=now,
                )
                # Reject collisions with every original and prior replacement, including rejected ideas.
                if any(batch_distinctness_issues([other, candidate_item]) for other in all_items):
                    continue
                chosen = (candidate, novelty, candidate_item)
                break
            if chosen is None:
                raise RecoveryConflict("No fresh replacement remains in this batch's governed candidate pool")
            candidate, novelty, replacement_item = chosen
            new_plan = ContentPlanV1(
                plan_id=str(uuid4()), candidate_id=candidate.candidate_id,
                profile_id=item.profile_id, profile_version=item.profile_version,
                role=candidate.role, canonical_topic=novelty.canonical_topic,
                subtopics=candidate.subtopics, angle=candidate.angle, target_effect=candidate.target_effect,
                format=candidate.tentative_format, hook_pattern=candidate.hook_pattern,
                novelty_result_ref=novelty.novelty_result_id,
                planning_rationale=candidate.rationale,
            )
            entry = ReplacementPlanV1(
                recovery_id=str(uuid4()), tenant_id=tenant_id, batch_id=item.batch_id,
                rejected_content_id=content_id, rejected_plan_id=run.plan_id, rejected_plan_digest=run.plan_digest,
                failed_run_id=run.run_id, failure=run.failure, profile_snapshot_digest=profile.digest,
                planning_trace_digest=trace.digest, memory_ids=tuple(e.memory_id for e in memory), novelty=novelty,
                replacement_item=replacement_item,
                replacement_plan=PersistedContentPlan(
                    artifact_id=new_plan.plan_id, tenant_id=tenant_id, batch_id=item.batch_id,
                    content_id=replacement_item.content_id, plan=new_plan, digest=canonical_sha256(new_plan), created_at=now,
                ), created_at=now,
            )
            if await self.recovery.append(version, entry):
                await self.recovery.materialize(self.planning, entry)
                return entry
        raise RecoveryConflict("Batch recovery changed concurrently; reload and retry")
