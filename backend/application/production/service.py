from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from domain.planning.models import ContentPlanV1, canonical_sha256 as planning_sha256
from domain.profiles.models import ProfileVersion, canonical_digest as profile_digest
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    ClaimPublishability,
    ContentRevisionV1,
    ContentSpecV1,
    EditorialReviewV1,
    EditorialVerdict,
    GenerationFailureV1,
    GenerationRunState,
    GenerationRunV1,
    ResearchPackV1,
    ResearchVerdict,
    RevisionSource,
    RevisionStatus,
    canonical_sha256,
    utc_now,
)
from domain.production.ports import (
    EditorAgentPort,
    ProductionRepositoryPort,
    ResearchAgentPort,
    WriterAgentPort,
)


class ProductionAuthorityError(RuntimeError):
    pass


class ProductionDomainStop(RuntimeError):
    pass


class ProductionContractViolation(RuntimeError):
    pass


class RevisionBudgetExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class TextCellResult:
    run: GenerationRunV1
    revision: ContentRevisionV1
    research: ResearchPackV1
    content: ContentSpecV1
    review: EditorialReviewV1


class StructuredAgentCellService:
    """MK1 S3 text-production authority.

    The service owns orchestration/state decisions. Agent implementations only
    return typed artifacts plus safe attempt evidence; they never mutate MK1
    authoritative state themselves.
    """

    contract_versions = (
        "ResearchPackV1@1",
        "ContentSpecV1@1",
        "EditorialReviewV1@1",
        "GenerationRunV1@1",
        "ContentRevisionV1@1",
    )

    def __init__(
        self,
        *,
        repository: ProductionRepositoryPort,
        research_agent: ResearchAgentPort,
        writer_agent: WriterAgentPort,
        editor_agent: EditorAgentPort,
        max_editor_revision_cycles: int = 2,
    ):
        if max_editor_revision_cycles < 0 or max_editor_revision_cycles > 5:
            raise ValueError("max_editor_revision_cycles must be between 0 and 5")
        self.repository = repository
        self.research_agent = research_agent
        self.writer_agent = writer_agent
        self.editor_agent = editor_agent
        self.max_editor_revision_cycles = max_editor_revision_cycles

    async def produce_text(
        self,
        *,
        tenant_id: str,
        content_id: str,
        plan: ContentPlanV1,
        plan_digest: str,
        profile: ProfileVersion,
        parent_revision_id: str | None = None,
        now: datetime | None = None,
    ) -> TextCellResult:
        clock = now or utc_now()
        self.validate_authority(
            tenant_id=tenant_id,
            content_id=content_id,
            plan=plan,
            plan_digest=plan_digest,
            profile=profile,
        )

        run = GenerationRunV1(
            run_id=str(uuid4()),
            tenant_id=tenant_id,
            content_id=content_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_snapshot_digest=profile.digest,
            plan_id=plan.plan_id,
            plan_digest=plan_digest,
            state=GenerationRunState.CREATED,
            contract_versions=self.contract_versions,
            started_at=clock,
        )
        await self.repository.create_run(run)

        # RESEARCH
        run = await self._transition(run, GenerationRunState.RESEARCHING)
        research_input_digest = canonical_sha256(
            {
                "plan": plan.model_dump(mode="json"),
                "profile": profile.snapshot(),
            }
        )
        try:
            research_result = await self.research_agent.research(
                tenant_id=tenant_id,
                run_id=run.run_id,
                plan=plan,
                profile=profile,
            )
        except Exception as exc:
            run = await self._fail_run(run, "RESEARCH_AGENT_FAILED", "research", retryable=True)
            await self._persist_exception_attempts(
                run=run,
                expected_agent=AgentKind.RESEARCH,
                expected_input_digest=research_input_digest,
                exc=exc,
            )
            raise ProductionContractViolation(
                "Research agent failed before producing a valid typed artifact"
            ) from exc

        research = research_result.artifact
        research_digest = canonical_sha256(research)
        try:
            research_refs = await self._persist_attempts(
                run=run,
                expected_agent=AgentKind.RESEARCH,
                attempts=research_result.attempts,
                expected_input_digest=research_input_digest,
                expected_output_digest=research_digest,
            )
            run = await self._bind_attempt_refs(run, research_refs)
            self._verify_research(plan, research)
        except ProductionContractViolation:
            await self._fail_run(
                run,
                "RESEARCH_CONTRACT_VIOLATION",
                "research",
                retryable=False,
            )
            raise

        await self.repository.save_artifact(
            tenant_id=tenant_id,
            run_id=run.run_id,
            artifact_type="ResearchPackV1",
            artifact_id=research.research_id,
            digest=research_digest,
            payload=research.model_dump(mode="json"),
        )
        run = run.model_copy(update={"research_pack_ref": research.research_id})
        await self.repository.update_run(run)

        if research.verdict == ResearchVerdict.NO_GO:
            await self._fail_run(
                run,
                "RESEARCH_NO_GO",
                "research",
                retryable=False,
                safe_message="Research policy rejected the plan for production.",
            )
            raise ProductionDomainStop("Research verdict NO_GO")

        # WRITER
        run = await self._transition(run, GenerationRunState.WRITING)
        writer_input_digest = canonical_sha256(
            {
                "plan": plan.model_dump(mode="json"),
                "profile": profile.snapshot(),
                "research": research.model_dump(mode="json"),
            }
        )
        try:
            writer_result = await self.writer_agent.write(
                tenant_id=tenant_id,
                run_id=run.run_id,
                plan=plan,
                profile=profile,
                research=research,
            )
        except Exception as exc:
            run = await self._fail_run(run, "WRITER_AGENT_FAILED", "writing", retryable=True)
            await self._persist_exception_attempts(
                run=run,
                expected_agent=AgentKind.WRITER,
                expected_input_digest=writer_input_digest,
                exc=exc,
            )
            raise ProductionContractViolation(
                "Writer agent failed before producing a valid typed artifact"
            ) from exc

        content = writer_result.artifact
        content_digest = canonical_sha256(content)
        try:
            writer_refs = await self._persist_attempts(
                run=run,
                expected_agent=AgentKind.WRITER,
                attempts=writer_result.attempts,
                expected_input_digest=writer_input_digest,
                expected_output_digest=content_digest,
            )
            run = await self._bind_attempt_refs(run, writer_refs)
            self._verify_content(plan, profile, research, content)
        except ProductionContractViolation:
            await self._fail_run(
                run,
                "WRITER_CONTRACT_VIOLATION",
                "writing",
                retryable=False,
            )
            raise

        await self.repository.save_artifact(
            tenant_id=tenant_id,
            run_id=run.run_id,
            artifact_type="ContentSpecV1",
            artifact_id=content.content_spec_id,
            digest=content_digest,
            payload=content.model_dump(mode="json"),
        )
        run = run.model_copy(update={"content_spec_ref": content.content_spec_id})
        await self.repository.update_run(run)

        # EDITOR
        run = await self._transition(run, GenerationRunState.EDITING)
        final_review: EditorialReviewV1 | None = None

        for revision_cycle in range(self.max_editor_revision_cycles + 1):
            editor_input_digest = canonical_sha256(
                {
                    "plan": plan.model_dump(mode="json"),
                    "profile": profile.snapshot(),
                    "research": research.model_dump(mode="json"),
                    "content": content.model_dump(mode="json"),
                    "revision_cycle": revision_cycle,
                }
            )
            try:
                editor_result = await self.editor_agent.edit(
                    tenant_id=tenant_id,
                    run_id=run.run_id,
                    plan=plan,
                    profile=profile,
                    research=research,
                    content=content,
                    revision_cycle=revision_cycle,
                )
            except Exception as exc:
                run = await self._fail_run(run, "EDITOR_AGENT_FAILED", "editing", retryable=True)
                await self._persist_exception_attempts(
                    run=run,
                    expected_agent=AgentKind.EDITOR,
                    expected_input_digest=editor_input_digest,
                    exc=exc,
                )
                raise ProductionContractViolation(
                    "Editor agent failed before producing a valid typed artifact"
                ) from exc

            review = editor_result.artifact
            review_digest = canonical_sha256(review)
            try:
                editor_refs = await self._persist_attempts(
                    run=run,
                    expected_agent=AgentKind.EDITOR,
                    attempts=editor_result.attempts,
                    expected_input_digest=editor_input_digest,
                    expected_output_digest=review_digest,
                )
                run = await self._bind_attempt_refs(run, editor_refs)
                self._verify_review(plan, research, content, review)
            except ProductionContractViolation:
                await self._fail_run(
                    run,
                    "EDITOR_CONTRACT_VIOLATION",
                    "editing",
                    retryable=False,
                )
                raise

            await self.repository.save_artifact(
                tenant_id=tenant_id,
                run_id=run.run_id,
                artifact_type="EditorialReviewV1",
                artifact_id=review.review_id,
                digest=review_digest,
                payload=review.model_dump(mode="json"),
            )
            run = run.model_copy(update={"editorial_review_ref": review.review_id})
            await self.repository.update_run(run)

            if review.verdict == EditorialVerdict.REJECT:
                await self._fail_run(
                    run,
                    "EDITOR_REJECTED",
                    "editing",
                    retryable=False,
                    safe_message="Editorial policy rejected the generated text.",
                )
                raise ProductionDomainStop("Editor verdict REJECT")

            if review.verdict == EditorialVerdict.APPROVE_TEXT:
                final_review = review
                break

            if revision_cycle >= self.max_editor_revision_cycles:
                await self._fail_run(
                    run,
                    "EDITOR_REVISION_BUDGET_EXHAUSTED",
                    "editing",
                    retryable=False,
                    safe_message="The bounded editorial revision budget was exhausted.",
                )
                raise RevisionBudgetExhausted("Editor revision budget exhausted")

            revised = review.revised_content_spec
            if revised is None:
                await self._fail_run(
                    run,
                    "EDITOR_REVISION_MISSING",
                    "editing",
                    retryable=False,
                    safe_message="Editor requested revision without a typed revised ContentSpec.",
                )
                raise ProductionContractViolation("REVISE requires revised_content_spec")

            try:
                self._verify_content(plan, profile, research, revised)
                if revised.content_spec_id == content.content_spec_id:
                    raise ProductionContractViolation(
                        "Editor revision must create a new ContentSpec identity"
                    )
            except ProductionContractViolation:
                await self._fail_run(
                    run,
                    "EDITOR_REVISION_CONTRACT_VIOLATION",
                    "editing",
                    retryable=False,
                    safe_message="Editor revision violated frozen content authority.",
                )
                raise

            content = revised
            content_digest = canonical_sha256(content)
            await self.repository.save_artifact(
                tenant_id=tenant_id,
                run_id=run.run_id,
                artifact_type="ContentSpecV1",
                artifact_id=content.content_spec_id,
                digest=content_digest,
                payload=content.model_dump(mode="json"),
            )
            run = run.model_copy(update={"content_spec_ref": content.content_spec_id})
            await self.repository.update_run(run)

        if final_review is None:
            await self._fail_run(
                run,
                "EDITOR_TERMINAL_VERDICT_MISSING",
                "editing",
                retryable=False,
            )
            raise ProductionContractViolation("Editor loop exited without a terminal verdict")

        final_content_digest = canonical_sha256(content)
        revision = ContentRevisionV1(
            revision_id=str(uuid4()),
            tenant_id=tenant_id,
            content_id=content_id,
            run_id=run.run_id,
            parent_revision_id=parent_revision_id,
            source=RevisionSource.GENERATION,
            content_spec_ref=content.content_spec_id,
            content_spec_digest=final_content_digest,
            status=RevisionStatus.DRAFT,
            created_at=clock,
        )
        await self.repository.save_revision(revision)

        # S3 hands a validated text revision to S4. The GenerationRun is kept
        # open in the frozen next state rather than fabricating full completion.
        run = await self._transition(run, GenerationRunState.VISUAL_PLANNING)
        return TextCellResult(
            run=run,
            revision=revision,
            research=research,
            content=content,
            review=final_review,
        )

    def validate_authority(
        self,
        *,
        tenant_id: str,
        content_id: str,
        plan: ContentPlanV1,
        plan_digest: str,
        profile: ProfileVersion,
    ) -> None:
        if not tenant_id.strip() or not content_id.strip():
            raise ProductionAuthorityError("tenant_id and content_id are required")
        if profile.tenant_id != tenant_id:
            raise ProductionAuthorityError("ProfileVersion tenant authority mismatch")
        if plan.profile_id != profile.profile_id or plan.profile_version != profile.version:
            raise ProductionAuthorityError("ContentPlan/ProfileVersion authority mismatch")
        if planning_sha256(plan) != plan_digest:
            raise ProductionAuthorityError("ContentPlan digest mismatch")
        if profile_digest(profile) != profile.digest:
            raise ProductionAuthorityError("ProfileVersion digest mismatch")

    @staticmethod
    def _verify_research(plan: ContentPlanV1, research: ResearchPackV1) -> None:
        if research.plan_id != plan.plan_id:
            raise ProductionContractViolation("ResearchPack plan_id mismatch")

    @staticmethod
    def _verify_content(
        plan: ContentPlanV1,
        profile: ProfileVersion,
        research: ResearchPackV1,
        content: ContentSpecV1,
    ) -> None:
        if content.plan_id != plan.plan_id:
            raise ProductionContractViolation("ContentSpec plan_id mismatch")
        if content.format != plan.format:
            raise ProductionContractViolation(
                "ContentSpec format cannot silently change the ContentPlan format"
            )
        if content.language != profile.copy_policy.target_language:
            raise ProductionContractViolation(
                "ContentSpec language does not match frozen ProfileVersion copy policy"
            )

        claims = {item.claim_id: item for item in research.claims}
        unknown = set(content.claims_used) - set(claims)
        if unknown:
            raise ProductionContractViolation(
                f"ContentSpec references unknown claim IDs: {sorted(unknown)}"
            )
        forbidden = {
            claim_id
            for claim_id in content.claims_used
            if claims[claim_id].publishability == ClaimPublishability.FORBIDDEN
        }
        if forbidden:
            raise ProductionContractViolation(
                f"ContentSpec references forbidden claim IDs: {sorted(forbidden)}"
            )

    @classmethod
    def _verify_review(
        cls,
        plan: ContentPlanV1,
        research: ResearchPackV1,
        content: ContentSpecV1,
        review: EditorialReviewV1,
    ) -> None:
        if review.revised_content_spec is not None:
            revised = review.revised_content_spec
            if revised.plan_id != plan.plan_id:
                raise ProductionContractViolation("Editor revision changed plan authority")
            claims = {item.claim_id: item for item in research.claims}
            unknown = set(revised.claims_used) - set(claims)
            if unknown:
                raise ProductionContractViolation(
                    f"Editor introduced unknown claim IDs: {sorted(unknown)}"
                )
            forbidden = {
                claim_id
                for claim_id in revised.claims_used
                if claims[claim_id].publishability == ClaimPublishability.FORBIDDEN
            }
            if forbidden:
                raise ProductionContractViolation(
                    f"Editor introduced forbidden claim IDs: {sorted(forbidden)}"
                )
        if (
            review.verdict == EditorialVerdict.APPROVE_TEXT
            and review.revised_content_spec is not None
            and canonical_sha256(review.revised_content_spec) != canonical_sha256(content)
        ):
            raise ProductionContractViolation(
                "APPROVE_TEXT cannot silently replace the reviewed ContentSpec"
            )

    async def _persist_attempts(
        self,
        *,
        run: GenerationRunV1,
        expected_agent: AgentKind,
        attempts: tuple[AgentAttemptEvidenceV1, ...],
        expected_input_digest: str,
        expected_output_digest: str,
    ) -> tuple[str, ...]:
        if not attempts:
            raise ProductionContractViolation("Agent attempt lineage is required")

        self._verify_attempt_envelope(
            attempts=attempts,
            expected_agent=expected_agent,
            expected_input_digest=expected_input_digest,
        )
        terminal = attempts[-1]
        if terminal.status != AgentAttemptStatus.SUCCESS:
            raise ProductionContractViolation(
                "Agent invocation must terminate with SUCCESS lineage"
            )
        if terminal.output_digest != expected_output_digest:
            raise ProductionContractViolation(
                "Agent success output digest does not bind the typed artifact"
            )

        for attempt in attempts:
            await self.repository.append_agent_attempt(run.tenant_id, run.run_id, attempt)
        return tuple(item.agent_run_id for item in attempts)

    async def _persist_exception_attempts(
        self,
        *,
        run: GenerationRunV1,
        expected_agent: AgentKind,
        expected_input_digest: str,
        exc: Exception,
    ) -> tuple[str, ...]:
        attempts = tuple(getattr(exc, "attempts", ()) or ())
        if not attempts:
            return ()
        self._verify_attempt_envelope(
            attempts=attempts,
            expected_agent=expected_agent,
            expected_input_digest=expected_input_digest,
        )
        if any(item.status == AgentAttemptStatus.SUCCESS for item in attempts):
            raise ProductionContractViolation(
                "A failed agent invocation cannot carry SUCCESS terminal evidence"
            )
        for attempt in attempts:
            await self.repository.append_agent_attempt(run.tenant_id, run.run_id, attempt)
        refs = tuple(item.agent_run_id for item in attempts)
        await self._bind_attempt_refs(run, refs)
        return refs

    @staticmethod
    def _verify_attempt_envelope(
        *,
        attempts: tuple[AgentAttemptEvidenceV1, ...],
        expected_agent: AgentKind,
        expected_input_digest: str,
    ) -> None:
        ids = [item.agent_run_id for item in attempts]
        if len(ids) != len(set(ids)):
            raise ProductionContractViolation(
                "agent_run_id values must be unique per invocation"
            )
        if any(item.agent != expected_agent for item in attempts):
            raise ProductionContractViolation(
                "Agent attempt lineage contains the wrong agent identity"
            )
        if any(item.input_digest != expected_input_digest for item in attempts):
            raise ProductionContractViolation(
                "Agent attempt input digest does not bind the authoritative input"
            )
        ordinals = [item.attempt for item in attempts]
        if ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
            raise ProductionContractViolation(
                "Agent attempt ordinals must be unique and monotonic"
            )

    async def _bind_attempt_refs(
        self,
        run: GenerationRunV1,
        refs: tuple[str, ...],
    ) -> GenerationRunV1:
        if not refs:
            return run
        existing = set(run.agent_run_refs)
        merged = run.agent_run_refs + tuple(ref for ref in refs if ref not in existing)
        updated = run.model_copy(update={"agent_run_refs": merged})
        await self.repository.update_run(updated)
        return updated

    async def _transition(
        self,
        run: GenerationRunV1,
        state: GenerationRunState,
    ) -> GenerationRunV1:
        updated = run.model_copy(update={"state": state})
        await self.repository.update_run(updated)
        return updated

    async def _fail_run(
        self,
        run: GenerationRunV1,
        code: str,
        stage: str,
        *,
        retryable: bool,
        safe_message: str = (
            "A production stage failed before a valid authoritative artifact was produced."
        ),
    ) -> GenerationRunV1:
        failed = run.model_copy(
            update={
                "state": GenerationRunState.FAILED,
                "failure": GenerationFailureV1(
                    code=code,
                    stage=stage,
                    retryable=retryable,
                    safe_message=safe_message,
                ),
                "completed_at": utc_now(),
            }
        )
        await self.repository.update_run(failed)
        return failed
