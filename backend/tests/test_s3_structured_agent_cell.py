from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from application.production.service import (
    ProductionAuthorityError,
    ProductionContractViolation,
    ProductionDomainStop,
    RevisionBudgetExhausted,
    StructuredAgentCellService,
)
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
    ClaimCategory,
    ClaimConfidence,
    ClaimPublishability,
    ClaimV1,
    ContentSpecV1,
    EditorialCheck,
    EditorialReviewV1,
    EditorialVerdict,
    EvidenceRefV1,
    EvidenceSourceType,
    EvidenceTrustLevel,
    GenerationRunState,
    ResearchPackV1,
    ResearchVerdict,
    RevisionStatus,
    TextFormatSpecV1,
    canonical_sha256,
)
from domain.production.ports import AgentInvocationResult


NOW = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)


def make_profile(*, tenant_id: str = "tenant-1") -> ProfileVersion:
    profile = ProfileVersion(
        profile_id="profile-1",
        tenant_id=tenant_id,
        version=1,
        identity=ProfileIdentity(
            name="Logan Identity",
            account_type=AccountType.NICHE,
            summary="Automotive education profile",
        ),
        goals=(Goal.EDUCATE,),
        audience=("drivers who want safer cars",),
        editorial_strategy=EditorialStrategy(topic_families=("automotive safety",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(
            voice_traits=("clear", "practical"),
            target_language="es",
        ),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean",)),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.INSTAGRAM,),
            default_batch_size=4,
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return profile.model_copy(update={"digest": profile_digest(profile)})


def make_plan(profile: ProfileVersion) -> ContentPlanV1:
    return ContentPlanV1(
        plan_id="plan-1",
        candidate_id="candidate-1",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        role="education",
        canonical_topic="automotive.safety",
        subtopics=("braking distance",),
        angle="how it works",
        target_effect="help drivers understand a safety mechanism",
        format="text",
        hook_pattern="question",
        visual_pattern_hint=None,
        novelty_result_ref="novelty-1",
        planning_rationale="fresh educational direction",
    )


def make_research(plan: ContentPlanV1, *, verdict: ResearchVerdict = ResearchVerdict.GO) -> ResearchPackV1:
    evidence = EvidenceRefV1(
        evidence_id="evidence-1",
        source_type=EvidenceSourceType.OFFICIAL_DOC,
        title="Fixture official source",
        locator="fixture://official/source",
        observed_at=NOW,
        trusted_level=EvidenceTrustLevel.PRIMARY,
    )
    claim = ClaimV1(
        claim_id="claim-1",
        statement="A supported fixture claim.",
        category=ClaimCategory.FACTUAL,
        confidence=ClaimConfidence.HIGH,
        evidence_refs=(evidence.evidence_id,),
        publishability=ClaimPublishability.ALLOWED,
    )
    forbidden = ClaimV1(
        claim_id="claim-forbidden",
        statement="A claim that policy forbids publishing.",
        category=ClaimCategory.FACTUAL,
        confidence=ClaimConfidence.LOW,
        evidence_refs=(evidence.evidence_id,),
        publishability=ClaimPublishability.FORBIDDEN,
    )
    return ResearchPackV1(
        research_id="research-1",
        plan_id=plan.plan_id,
        verdict=verdict,
        key_points=("Use the supported claim only.",),
        claims=(claim, forbidden),
        evidence=(evidence,),
        forbidden_claims=(forbidden.statement,),
    )


def make_content(
    plan: ContentPlanV1,
    *,
    content_spec_id: str = "content-spec-1",
    claims_used: tuple[str, ...] = ("claim-1",),
) -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id=content_spec_id,
        plan_id=plan.plan_id,
        language="es",
        title="Cómo pensar una decisión de seguridad",
        hook="¿Qué cambia realmente cuando entiendes el mecanismo?",
        body="Este texto usa únicamente la afirmación respaldada por el ResearchPack.",
        cta="Guárdalo para revisarlo luego.",
        hashtags=("#SeguridadAutomotriz",),
        format="text",
        format_spec=TextFormatSpecV1(),
        claims_used=claims_used,
    )


def make_review(
    *,
    review_id: str,
    verdict: EditorialVerdict,
    revised_content_spec: ContentSpecV1 | None = None,
) -> EditorialReviewV1:
    return EditorialReviewV1(
        review_id=review_id,
        verdict=verdict,
        brand_match=EditorialCheck.PASS,
        clarity=EditorialCheck.PASS,
        hook_strength=EditorialCheck.PASS,
        factual_consistency=EditorialCheck.PASS,
        platform_fit=EditorialCheck.PASS,
        revised_content_spec=revised_content_spec,
    )


def make_attempt(agent: AgentKind, input_digest: str, artifact, *, attempt: int = 1) -> AgentAttemptEvidenceV1:
    return AgentAttemptEvidenceV1(
        agent_run_id=str(uuid4()),
        agent=agent,
        contract_version=f"{artifact.__class__.__name__}@1",
        prompt_version="s3-test-v1",
        provider="fixture",
        model="fixture-model",
        attempt=attempt,
        latency_ms=3,
        input_digest=input_digest,
        output_digest=canonical_sha256(artifact),
        input_tokens=10,
        output_tokens=20,
        cost_usd=0,
        status=AgentAttemptStatus.SUCCESS,
        created_at=NOW,
    )


class InMemoryProductionRepository:
    def __init__(self):
        self.runs = {}
        self.attempts = []
        self.artifacts = []
        self.revisions = []

    async def create_run(self, run):
        assert run.run_id not in self.runs
        self.runs[run.run_id] = run

    async def get_run(self, tenant_id, run_id):
        run = self.runs.get(run_id)
        if run is None or run.tenant_id != tenant_id:
            return None
        return run

    async def update_run(self, run):
        assert run.run_id in self.runs
        self.runs[run.run_id] = run

    async def append_agent_attempt(self, tenant_id, run_id, attempt):
        assert self.runs[run_id].tenant_id == tenant_id
        self.attempts.append((run_id, attempt))

    async def save_artifact(self, **kwargs):
        assert self.runs[kwargs["run_id"]].tenant_id == kwargs["tenant_id"]
        self.artifacts.append(kwargs)

    async def save_revision(self, revision):
        assert self.runs[revision.run_id].tenant_id == revision.tenant_id
        self.revisions.append(revision)


class FixtureResearchAgent:
    def __init__(self, artifact: ResearchPackV1):
        self.artifact = artifact
        self.calls = 0

    async def research(self, *, tenant_id, run_id, plan, profile):
        self.calls += 1
        input_digest = canonical_sha256(
            {"plan": plan.model_dump(mode="json"), "profile": profile.snapshot()}
        )
        return AgentInvocationResult(
            artifact=self.artifact,
            attempts=(make_attempt(AgentKind.RESEARCH, input_digest, self.artifact),),
        )


class FixtureWriterAgent:
    def __init__(self, artifact: ContentSpecV1):
        self.artifact = artifact
        self.calls = 0

    async def write(self, *, tenant_id, run_id, plan, profile, research):
        self.calls += 1
        input_digest = canonical_sha256(
            {
                "plan": plan.model_dump(mode="json"),
                "profile": profile.snapshot(),
                "research": research.model_dump(mode="json"),
            }
        )
        return AgentInvocationResult(
            artifact=self.artifact,
            attempts=(make_attempt(AgentKind.WRITER, input_digest, self.artifact),),
        )


class FixtureEditorAgent:
    def __init__(self, reviews: list[EditorialReviewV1]):
        self.reviews = reviews
        self.calls = 0

    async def edit(self, *, tenant_id, run_id, plan, profile, research, content, revision_cycle):
        review = self.reviews[min(self.calls, len(self.reviews) - 1)]
        self.calls += 1
        input_digest = canonical_sha256(
            {
                "plan": plan.model_dump(mode="json"),
                "profile": profile.snapshot(),
                "research": research.model_dump(mode="json"),
                "content": content.model_dump(mode="json"),
                "revision_cycle": revision_cycle,
            }
        )
        return AgentInvocationResult(
            artifact=review,
            attempts=(make_attempt(AgentKind.EDITOR, input_digest, review),),
        )


def make_service(*, research, content, reviews, max_editor_revision_cycles=2):
    repository = InMemoryProductionRepository()
    service = StructuredAgentCellService(
        repository=repository,
        research_agent=FixtureResearchAgent(research),
        writer_agent=FixtureWriterAgent(content),
        editor_agent=FixtureEditorAgent(reviews),
        max_editor_revision_cycles=max_editor_revision_cycles,
    )
    return service, repository


@pytest.mark.asyncio
async def test_text_cell_creates_typed_lineage_and_hands_off_to_s4():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan)
    content = make_content(plan)
    review = make_review(review_id="review-1", verdict=EditorialVerdict.APPROVE_TEXT)
    service, repository = make_service(research=research, content=content, reviews=[review])

    result = await service.produce_text(
        tenant_id=profile.tenant_id,
        content_id="content-1",
        plan=plan,
        plan_digest=planning_sha256(plan),
        profile=profile,
        now=NOW,
    )

    assert result.run.state == GenerationRunState.VISUAL_PLANNING
    assert result.run.completed_at is None
    assert result.revision.status == RevisionStatus.DRAFT
    assert result.revision.content_spec_digest == canonical_sha256(content)
    assert len(repository.attempts) == 3
    assert [item["artifact_type"] for item in repository.artifacts] == [
        "ResearchPackV1",
        "ContentSpecV1",
        "EditorialReviewV1",
    ]
    assert repository.runs[result.run.run_id].state == GenerationRunState.VISUAL_PLANNING


@pytest.mark.asyncio
async def test_research_no_go_stops_before_writer_and_persists_failed_run():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan, verdict=ResearchVerdict.NO_GO)
    content = make_content(plan)
    review = make_review(review_id="review-unused", verdict=EditorialVerdict.APPROVE_TEXT)
    service, repository = make_service(research=research, content=content, reviews=[review])

    with pytest.raises(ProductionDomainStop, match="NO_GO"):
        await service.produce_text(
            tenant_id=profile.tenant_id,
            content_id="content-1",
            plan=plan,
            plan_digest=planning_sha256(plan),
            profile=profile,
            now=NOW,
        )

    run = next(iter(repository.runs.values()))
    assert run.state == GenerationRunState.FAILED
    assert run.failure.code == "RESEARCH_NO_GO"
    assert len(repository.attempts) == 1
    assert len(repository.revisions) == 0


@pytest.mark.asyncio
async def test_writer_cannot_use_unknown_or_forbidden_claims():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan)

    for claims in (("invented-claim",), ("claim-forbidden",)):
        content = make_content(plan, claims_used=claims)
        review = make_review(review_id="review-unused", verdict=EditorialVerdict.APPROVE_TEXT)
        service, repository = make_service(research=research, content=content, reviews=[review])

        with pytest.raises(ProductionContractViolation):
            await service.produce_text(
                tenant_id=profile.tenant_id,
                content_id=f"content-{claims[0]}",
                plan=plan,
                plan_digest=planning_sha256(plan),
                profile=profile,
                now=NOW,
            )

        assert repository.revisions == []


@pytest.mark.asyncio
async def test_editor_cannot_introduce_unknown_claim_id():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan)
    content = make_content(plan)
    revised = make_content(
        plan,
        content_spec_id="content-spec-2",
        claims_used=("invented-by-editor",),
    )
    review = make_review(
        review_id="review-1",
        verdict=EditorialVerdict.REVISE,
        revised_content_spec=revised,
    )
    service, repository = make_service(research=research, content=content, reviews=[review])

    with pytest.raises(ProductionContractViolation, match="Editor introduced unknown claim IDs"):
        await service.produce_text(
            tenant_id=profile.tenant_id,
            content_id="content-1",
            plan=plan,
            plan_digest=planning_sha256(plan),
            profile=profile,
            now=NOW,
        )

    assert repository.revisions == []


@pytest.mark.asyncio
async def test_editor_revision_budget_is_bounded():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan)
    content = make_content(plan)
    revised_1 = make_content(plan, content_spec_id="content-spec-2")
    revised_2 = make_content(plan, content_spec_id="content-spec-3")
    reviews = [
        make_review(
            review_id="review-1",
            verdict=EditorialVerdict.REVISE,
            revised_content_spec=revised_1,
        ),
        make_review(
            review_id="review-2",
            verdict=EditorialVerdict.REVISE,
            revised_content_spec=revised_2,
        ),
    ]
    service, repository = make_service(
        research=research,
        content=content,
        reviews=reviews,
        max_editor_revision_cycles=1,
    )

    with pytest.raises(RevisionBudgetExhausted):
        await service.produce_text(
            tenant_id=profile.tenant_id,
            content_id="content-1",
            plan=plan,
            plan_digest=planning_sha256(plan),
            profile=profile,
            now=NOW,
        )

    run = next(iter(repository.runs.values()))
    assert run.state == GenerationRunState.FAILED
    assert run.failure.code == "EDITOR_REVISION_BUDGET_EXHAUSTED"
    assert len(repository.revisions) == 0


@pytest.mark.asyncio
async def test_tenant_or_digest_mismatch_never_creates_a_run():
    profile = make_profile()
    plan = make_plan(profile)
    research = make_research(plan)
    content = make_content(plan)
    review = make_review(review_id="review-1", verdict=EditorialVerdict.APPROVE_TEXT)
    service, repository = make_service(research=research, content=content, reviews=[review])

    with pytest.raises(ProductionAuthorityError):
        await service.produce_text(
            tenant_id="other-tenant",
            content_id="content-1",
            plan=plan,
            plan_digest=planning_sha256(plan),
            profile=profile,
            now=NOW,
        )
    with pytest.raises(ProductionAuthorityError):
        await service.produce_text(
            tenant_id=profile.tenant_id,
            content_id="content-1",
            plan=plan,
            plan_digest="f" * 64,
            profile=profile,
            now=NOW,
        )

    assert repository.runs == {}


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        ClaimV1.model_validate(
            {
                "claim_id": "claim-1",
                "statement": "supported",
                "category": "factual",
                "confidence": "high",
                "evidence_refs": [],
                "publishability": "allowed",
                "unexpected": "must fail closed",
            }
        )
