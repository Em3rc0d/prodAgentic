from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.production.service import ProductionContractViolation, StructuredAgentCellService
from domain.planning.models import ContentPlanV1, canonical_sha256 as planning_sha256
from domain.profiles.models import (
    AccountType,
    AgentPolicy,
    Channel,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    Goal,
    MigrationProvenance,
    NoveltyPolicy,
    ProfileIdentity,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    GenerationRunState,
    ResearchPackV1,
    ResearchVerdict,
    canonical_sha256,
)
from domain.production.ports import AgentInvocationResult


NOW = datetime(2026, 9, 8, 16, 0, tzinfo=timezone.utc)


def profile() -> ProfileVersion:
    value = ProfileVersion(
        profile_id="profile-lineage",
        tenant_id="tenant-lineage",
        version=1,
        identity=ProfileIdentity(
            name="Lineage fixture",
            account_type=AccountType.EDUCATION,
            summary="S3 failure-lineage fixture",
        ),
        goals=(Goal.EDUCATE,),
        audience=("engineers",),
        editorial_strategy=EditorialStrategy(topic_families=("systems",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("clear",), target_language="es"),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.MANUAL_EXPORT,), default_batch_size=1
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return value.model_copy(update={"digest": profile_digest(value)})


def plan(value: ProfileVersion) -> ContentPlanV1:
    return ContentPlanV1(
        plan_id="plan-lineage",
        candidate_id="candidate-lineage",
        profile_id=value.profile_id,
        profile_version=value.version,
        role="education",
        canonical_topic="systems",
        angle="how it works",
        target_effect="teach clearly",
        format="text",
        hook_pattern="question",
        novelty_result_ref="novelty-lineage",
        planning_rationale="failure-lineage fixture",
    )


class Repository:
    def __init__(self):
        self.runs = {}
        self.attempts = []

    async def create_run(self, run):
        self.runs[run.run_id] = run

    async def get_run(self, tenant_id, run_id):
        value = self.runs.get(run_id)
        return value if value and value.tenant_id == tenant_id else None

    async def update_run(self, run):
        self.runs[run.run_id] = run

    async def append_agent_attempt(self, tenant_id, run_id, attempt):
        assert self.runs[run_id].tenant_id == tenant_id
        self.attempts.append(attempt)

    async def save_artifact(self, **kwargs):
        raise AssertionError("failure-lineage fixtures must not save an authoritative artifact")

    async def save_revision(self, revision):
        raise AssertionError("failure-lineage fixtures must not create a revision")


class NeverCalledAgent:
    async def write(self, **kwargs):
        raise AssertionError("writer must not run")

    async def edit(self, **kwargs):
        raise AssertionError("editor must not run")


class InvocationFailure(RuntimeError):
    def __init__(self, attempts):
        super().__init__("fixture structured failure")
        self.attempts = attempts


class FailingResearchAgent:
    async def research(self, *, tenant_id, run_id, plan, profile):
        input_digest = canonical_sha256(
            {"plan": plan.model_dump(mode="json"), "profile": profile.snapshot()}
        )
        attempt = AgentAttemptEvidenceV1(
            agent_run_id="attempt-failed-1",
            agent=AgentKind.RESEARCH,
            contract_version="ResearchPackV1@1",
            prompt_version="s3-failure-fixture-v1",
            provider="fixture",
            model="fixture-model",
            attempt=1,
            latency_ms=1,
            input_digest=input_digest,
            output_digest="a" * 64,
            status=AgentAttemptStatus.CONTRACT_REPAIR,
            safe_failure_code="STRUCTURED_CONTRACT_INVALID",
            created_at=NOW,
        )
        raise InvocationFailure((attempt,))


class WrongPlanResearchAgent:
    async def research(self, *, tenant_id, run_id, plan, profile):
        artifact = ResearchPackV1(
            research_id="research-wrong-plan",
            plan_id="different-plan",
            verdict=ResearchVerdict.GO,
            key_points=("fixture",),
        )
        input_digest = canonical_sha256(
            {"plan": plan.model_dump(mode="json"), "profile": profile.snapshot()}
        )
        attempt = AgentAttemptEvidenceV1(
            agent_run_id="attempt-semantic-1",
            agent=AgentKind.RESEARCH,
            contract_version="ResearchPackV1@1",
            prompt_version="s3-semantic-fixture-v1",
            provider="fixture",
            model="fixture-model",
            attempt=1,
            latency_ms=1,
            input_digest=input_digest,
            output_digest=canonical_sha256(artifact),
            status=AgentAttemptStatus.SUCCESS,
            created_at=NOW,
        )
        return AgentInvocationResult(artifact=artifact, attempts=(attempt,))


def service(repository, research_agent):
    return StructuredAgentCellService(
        repository=repository,
        research_agent=research_agent,
        writer_agent=NeverCalledAgent(),
        editor_agent=NeverCalledAgent(),
    )


@pytest.mark.asyncio
async def test_failed_structured_invocation_persists_attempt_lineage_before_returning_failure():
    p = profile()
    cp = plan(p)
    repository = Repository()

    with pytest.raises(ProductionContractViolation):
        await service(repository, FailingResearchAgent()).produce_text(
            tenant_id=p.tenant_id,
            content_id="content-lineage",
            plan=cp,
            plan_digest=planning_sha256(cp),
            profile=p,
            now=NOW,
        )

    run = next(iter(repository.runs.values()))
    assert run.state == GenerationRunState.FAILED
    assert run.completed_at is not None
    assert run.failure.code == "RESEARCH_AGENT_FAILED"
    assert run.agent_run_refs == ("attempt-failed-1",)
    assert [item.agent_run_id for item in repository.attempts] == ["attempt-failed-1"]


@pytest.mark.asyncio
async def test_semantically_wrong_typed_artifact_keeps_success_attempt_but_fails_run():
    p = profile()
    cp = plan(p)
    repository = Repository()

    with pytest.raises(ProductionContractViolation, match="plan_id mismatch"):
        await service(repository, WrongPlanResearchAgent()).produce_text(
            tenant_id=p.tenant_id,
            content_id="content-semantic",
            plan=cp,
            plan_digest=planning_sha256(cp),
            profile=p,
            now=NOW,
        )

    run = next(iter(repository.runs.values()))
    assert run.state == GenerationRunState.FAILED
    assert run.completed_at is not None
    assert run.failure.code == "RESEARCH_CONTRACT_VIOLATION"
    assert run.agent_run_refs == ("attempt-semantic-1",)
    assert [item.agent_run_id for item in repository.attempts] == ["attempt-semantic-1"]
