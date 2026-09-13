from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.content_quality.brief import build_creative_brief
from application.content_quality.policy import blocking_publishability_issues, evaluate_publishability
from application.profiles.analyzer import DeterministicProfileAnalyzer
from application.production.service import ProductionContractViolation, StructuredAgentCellService
from application.visual.design_profile import derive_design_profile
from application.visual.planner import build_visual_spec
from core.demo import DemoWriterAgent
from domain.planning.models import ContentPlanV1
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
    ProfileSetup,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.production.models import (
    ContentSpecV1,
    EditorialReviewV1,
    EditorialVerdict,
    InfographicSectionV1,
    InfographicSpecV1,
    ResearchPackV1,
    ResearchVerdict,
    SingleImageSpecV1,
    TextFormatSpecV1,
)
from domain.visual.models import DiagramBlockV1


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def make_profile(
    *,
    account_type: AccountType = AccountType.EDUCATION,
    goals: tuple[Goal, ...] = (Goal.EDUCATE, Goal.BUILD_AUTHORITY),
    topics: tuple[str, ...] = ("systems engineering", "software architecture"),
    audience: tuple[str, ...] = ("systems engineering students",),
) -> ProfileVersion:
    value = ProfileVersion(
        profile_id="profile-r3",
        tenant_id="tenant-r3",
        version=1,
        identity=ProfileIdentity(
            name="EM3RC0D",
            account_type=account_type,
            summary="Practical systems engineering guidance",
        ),
        goals=goals,
        audience=audience,
        editorial_strategy=EditorialStrategy(topic_families=topics),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(
            voice_traits=("direct", "practical"),
            target_language="es",
            hook_tendencies=("question", "counterintuitive"),
            cta_style="question",
        ),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "bold")),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.LINKEDIN, Channel.MANUAL_EXPORT),
            default_batch_size=4,
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return value.model_copy(update={"digest": profile_digest(value)})


def make_plan(*, fmt: str = "single_image", role: str = "education") -> ContentPlanV1:
    return ContentPlanV1(
        plan_id=f"plan-r3-{fmt}",
        candidate_id="candidate-r3",
        profile_id="profile-r3",
        profile_version=1,
        role=role,
        canonical_topic="systems.engineering",
        subtopics=("systems engineering",),
        angle="worked example",
        target_effect="understanding",
        format=fmt,
        hook_pattern="question",
        visual_pattern_hint=None,
        novelty_result_ref="novelty-r3",
        planning_rationale="Cross-client R3 quality fixture",
    )


def make_text_content(*, body: str, title: str = "Una decisión técnica útil") -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-r3-text",
        plan_id="plan-r3-text",
        language="es",
        title=title,
        hook="¿Qué dato cambia realmente tu siguiente decisión técnica?",
        body=body,
        cta="¿Qué comprobarías antes de elegir?",
        format="text",
        format_spec=TextFormatSpecV1(),
        claims_used=(),
    )


def make_research(plan_id: str) -> ResearchPackV1:
    return ResearchPackV1(
        research_id="research-r3",
        plan_id=plan_id,
        verdict=ResearchVerdict.GO,
        key_points=("decision", "verification"),
        claims=(),
        evidence=(),
    )


def test_profile_analyzer_derives_compact_topics_without_adding_another_form():
    setup = ProfileSetup(
        name="Student Systems Guide",
        account_type=AccountType.EDUCATION,
        goals=(Goal.EDUCATE, Goal.BUILD_AUTHORITY),
        audience=(
            "people who want to pass the systems engineer career and systems engineer students in their last semester"
        ),
        voice=("direct", "practical"),
        channels=(Channel.LINKEDIN, Channel.MANUAL_EXPORT),
        examples=(),
    )

    proposal = DeterministicProfileAnalyzer().propose(setup)

    assert proposal.topic_families
    assert "systems engineer" in proposal.topic_families
    assert setup.audience not in proposal.topic_families
    assert all(len(topic.split()) <= 3 for topic in proposal.topic_families)


def test_creative_brief_is_profile_driven_not_vertical_hardcoded():
    education = make_profile()
    business = make_profile(
        account_type=AccountType.BUSINESS,
        goals=(Goal.SELL, Goal.BUILD_AUTHORITY),
        topics=("fleet maintenance",),
        audience=("small fleet operators",),
    )

    education_brief = build_creative_brief(plan=make_plan(), profile=education)
    business_plan = make_plan().model_copy(update={"canonical_topic": "fleet.maintenance", "subtopics": ("fleet maintenance",)})
    business_brief = build_creative_brief(plan=business_plan, profile=business)

    assert education_brief["identity"]["account_type"] == "education"
    assert business_brief["identity"]["account_type"] == "business"
    assert education_brief["audience"] != business_brief["audience"]
    assert "sell" in business_brief["goals"]
    assert all("automotive" not in rule.lower() and "systems" not in rule.lower() for rule in business_brief["quality_bar"])


def test_publishability_blocks_prodagentic_leaks_but_allows_real_technical_identifiers():
    profile = make_profile()
    plan = make_plan(fmt="text")
    legitimate = make_text_content(
        body=(
            "En una API real, user_id y retry_count pueden ser nombres legítimos. "
            "Lo importante es decidir qué condición observas, qué error toleras y qué evidencia confirma el resultado."
        )
    )
    assert not blocking_publishability_issues(content=legitimate, plan=plan, profile=profile)

    leaked = make_text_content(
        title="demo verificable",
        body=(
            "Este modo demo determinista valida el journey y deja better_decision antes de READY_FOR_REVIEW. "
            "El texto tiene suficiente longitud para que el único problema sea la fuga de autoridad interna."
        ),
    )
    codes = {issue.code for issue in blocking_publishability_issues(content=leaked, plan=plan, profile=profile)}
    assert "internal.demo_mode" in codes
    assert "internal.demo_verification" in codes
    assert "internal.state_name" in codes
    assert "copy.internal_token_leak" in codes


def test_editor_cannot_approve_copy_below_the_deterministic_publishability_floor():
    profile = make_profile()
    plan = make_plan(fmt="text")
    content = make_text_content(
        title="demo verificable",
        body=(
            "Este modo demo determinista explica un estado interno de prodAgentic y no debería superar el gate editorial. "
            "La regresión demuestra que un APPROVE_TEXT del modelo no puede saltarse la política determinista."
        ),
    )
    review = EditorialReviewV1(
        review_id="review-r3",
        verdict=EditorialVerdict.APPROVE_TEXT,
        brand_match="pass",
        clarity="pass",
        hook_strength="pass",
        factual_consistency="pass",
        platform_fit="pass",
        issues=(),
    )

    with pytest.raises(ProductionContractViolation, match="publishability floor"):
        StructuredAgentCellService._verify_review(
            plan,
            profile,
            make_research(plan.plan_id),
            content,
            review,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["text", "single_image", "carousel", "infographic"])
async def test_demo_writer_produces_clean_audience_facing_copy_for_every_format(fmt):
    profile = make_profile()
    plan = make_plan(fmt=fmt)
    research = make_research(plan.plan_id)

    result = await DemoWriterAgent().write(
        tenant_id=profile.tenant_id,
        run_id=f"run-{fmt}",
        plan=plan,
        profile=profile,
        research=research,
    )
    content = result.artifact
    visible = " ".join(filter(None, (content.title, content.hook, content.body, content.cta)))

    assert "demo verificable" not in visible.lower()
    assert "modo demo determinista" not in visible.lower()
    assert "journey r2" not in visible.lower()
    assert "better_decision" not in visible
    assert not blocking_publishability_issues(content=content, plan=plan, profile=profile)


def test_visual_direction_uses_semantic_diagrams_without_inventing_copy():
    profile = make_profile()
    design = derive_design_profile(profile)
    content = ContentSpecV1(
        content_spec_id="content-r3-visual",
        plan_id="plan-r3-single_image",
        language="es",
        title="Tres pasos",
        hook="Tres pasos para decidir mejor.",
        body="Define, filtra y actúa con evidencia suficiente.",
        format="single_image",
        format_spec=SingleImageSpecV1(
            headline="Tres pasos para una decisión más clara",
            supporting_copy=("Define la decisión", "Reduce el ruido", "Elige la siguiente acción"),
            footer="EM3RC0D",
        ),
    )

    spec = build_visual_spec(
        visual_spec_id="vs-r3",
        revision_id="revision-r3",
        content=content,
        design_profile=design,
    )

    diagrams = [block for block in spec.pages[0].blocks if isinstance(block, DiagramBlockV1)]
    assert spec.visual_pattern == "single_image.action_framework.v2"
    assert len(diagrams) == 1
    assert diagrams[0].label_refs == (
        "content_spec.format_spec.supporting_copy[0]",
        "content_spec.format_spec.supporting_copy[1]",
        "content_spec.format_spec.supporting_copy[2]",
    )


def test_publishability_reports_soft_quality_risks_without_false_blocking():
    profile = make_profile()
    plan = make_plan(fmt="infographic")
    content = ContentSpecV1(
        content_spec_id="content-r3-info",
        plan_id=plan.plan_id,
        language="es",
        title="Una guía",
        hook="Una forma clara de pensar una decisión técnica.",
        body="Primero define qué cambia la decisión y después elige una comprobación concreta antes de ejecutar el siguiente paso.",
        format="infographic",
        format_spec=InfographicSpecV1(
            title="Una guía práctica",
            sections=(InfographicSectionV1(section_id="one", label="Decisión", value_or_copy="Define qué cambia"),),
        ),
    )

    issues = evaluate_publishability(content=content, plan=plan, profile=profile)
    codes = {issue.code for issue in issues}
    assert "copy.generic_hook" in codes
    assert "visual.infographic_too_thin" in codes
    assert not blocking_publishability_issues(content=content, plan=plan, profile=profile)
