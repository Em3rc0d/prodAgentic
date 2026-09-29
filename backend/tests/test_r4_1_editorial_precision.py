from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.content_quality.policy import factual_precision_issues
from application.production.r4_service import R4StructuredAgentCellService
from application.production.service import ProductionContractViolation
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
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.production.models import (
    ClaimCategory,
    ClaimConfidence,
    ClaimPublishability,
    ClaimV1,
    ContentSpecV1,
    EditorialReviewV1,
    EvidenceRefV1,
    EvidenceSourceType,
    EvidenceTrustLevel,
    ResearchPackV1,
    ResearchVerdict,
    TextFormatSpecV1,
)


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _profile() -> ProfileVersion:
    provisional = ProfileVersion(
        profile_id="profile-precision",
        tenant_id="tenant-precision",
        version=1,
        identity=ProfileIdentity(
            name="EM3RC0D",
            account_type=AccountType.EDUCATION,
            summary="Practical systems engineering guidance",
        ),
        goals=(Goal.EDUCATE, Goal.BUILD_AUTHORITY),
        audience=("systems engineering students",),
        editorial_strategy=EditorialStrategy(topic_families=("infrastructure",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(
            voice_traits=("direct", "practical"),
            target_language="es",
        ),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "technical")),
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
    return provisional.model_copy(update={"digest": profile_digest(provisional)})


def _plan() -> ContentPlanV1:
    return ContentPlanV1(
        plan_id="plan-precision",
        candidate_id="candidate-precision",
        profile_id="profile-precision",
        profile_version=1,
        role="education",
        canonical_topic="infrastructure.as.code",
        subtopics=("infrastructure as code",),
        angle="what changes operationally",
        target_effect="understanding",
        format="text",
        hook_pattern="counterintuitive",
        visual_pattern_hint=None,
        novelty_result_ref="novelty-precision",
        planning_rationale="Precision regression",
    )


def _research(*, strong_support: bool = False, uncertainty: bool = False) -> ResearchPackV1:
    statement = (
        "La automatización garantiza entornos idénticos y consistentes."
        if strong_support
        else "La infraestructura como código permite definir y repetir configuraciones mediante archivos versionables."
    )
    claim = ClaimV1(
        claim_id="claim-1",
        statement=statement,
        category=ClaimCategory.FACTUAL,
        confidence=ClaimConfidence.HIGH if strong_support else ClaimConfidence.MEDIUM,
        evidence_refs=("evidence-1",),
        publishability=ClaimPublishability.ALLOWED,
    )
    evidence = EvidenceRefV1(
        evidence_id="evidence-1",
        source_type=EvidenceSourceType.OFFICIAL_DOC,
        title="Official infrastructure documentation",
        locator="https://example.invalid/docs",
        observed_at=NOW,
        trusted_level=EvidenceTrustLevel.PRIMARY,
    )
    return ResearchPackV1(
        research_id="research-precision",
        plan_id="plan-precision",
        verdict=ResearchVerdict.GO,
        key_points=("IaC makes configuration declarative and repeatable.",),
        claims=(claim,),
        evidence=(evidence,),
        uncertainties=("Exact environment identity depends on surrounding state.",) if uncertainty else (),
    )


def _content(body: str) -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-precision",
        plan_id="plan-precision",
        language="es",
        title="Qué cambia con infraestructura como código",
        hook="IaC cambia cómo declaras y revisas infraestructura.",
        body=body,
        cta="¿Qué parte de tu infraestructura ya administras como código?",
        format="text",
        format_spec=TextFormatSpecV1(),
        claims_used=("claim-1",),
    )


def _approve() -> EditorialReviewV1:
    return EditorialReviewV1(
        review_id="review-precision",
        verdict="APPROVE_TEXT",
        brand_match="pass",
        clarity="pass",
        hook_strength="pass",
        factual_consistency="pass",
        platform_fit="pass",
        issues=(),
    )


def test_absolute_wording_is_blocked_when_it_strengthens_medium_confidence_research():
    content = _content(
        "IaC garantiza que desarrollo, prueba y producción sean idénticos y consistentes, "
        "eliminando por completo la necesidad de ajustes manuales."
    )

    issues = factual_precision_issues(
        content=content,
        research=_research(),
    )

    assert {item.code for item in issues} == {"factual.modality_escalation"}


def test_absolute_wording_requires_equivalent_high_confidence_research_authority():
    content = _content(
        "La automatización garantiza entornos idénticos y consistentes."
    )

    assert factual_precision_issues(
        content=content,
        research=_research(strong_support=True),
    ) == ()

    assert {
        item.code
        for item in factual_precision_issues(
            content=content,
            research=_research(strong_support=True, uncertainty=True),
        )
    } == {"factual.modality_escalation"}


def test_r4_editor_cannot_approve_modality_escalation():
    content = _content(
        "IaC garantiza entornos idénticos y consistentes y elimina por completo los ajustes manuales."
    )

    with pytest.raises(
        ProductionContractViolation,
        match="factual.modality_escalation",
    ):
        R4StructuredAgentCellService._verify_review(
            _plan(),
            _profile(),
            _research(),
            content,
            _approve(),
        )
