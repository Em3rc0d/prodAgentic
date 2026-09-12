from __future__ import annotations

import os
from uuid import uuid4

from application.production.service import StructuredAgentCellService
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    CarouselSlideV1,
    CarouselSpecV1,
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
    InfographicSectionV1,
    InfographicSpecV1,
    ResearchPackV1,
    ResearchVerdict,
    SingleImageSpecV1,
    TextFormatSpecV1,
    canonical_sha256,
    utc_now,
)
from domain.production.ports import AgentInvocationResult


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def demo_mode_enabled() -> bool:
    environment = os.getenv("PRODAGENTIC_ENV", "development").strip().lower()
    return environment != "production" and _truthy(os.getenv("PRODAGENTIC_DEMO_MODE"))


def _attempt(agent: AgentKind, input_digest: str, artifact) -> AgentAttemptEvidenceV1:
    return AgentAttemptEvidenceV1(
        agent_run_id=str(uuid4()),
        agent=agent,
        contract_version=f"{artifact.__class__.__name__}@1",
        prompt_version="mk1-r2-demo-v1",
        provider="deterministic-demo",
        model="fixture-v1",
        attempt=1,
        latency_ms=0,
        input_digest=input_digest,
        output_digest=canonical_sha256(artifact),
        input_tokens=0,
        output_tokens=0,
        cost_usd=0,
        status=AgentAttemptStatus.SUCCESS,
        created_at=utc_now(),
    )


class DemoResearchAgent:
    async def research(self, *, tenant_id, run_id, plan, profile):
        evidence = EvidenceRefV1(
            evidence_id=f"demo-evidence-{run_id}",
            source_type=EvidenceSourceType.USER_PROVIDED,
            title="Deterministic R2 demo evidence",
            locator="demo://mk1-r2/local-fixture",
            observed_at=utc_now(),
            trusted_level=EvidenceTrustLevel.PRIMARY,
            notes="Local test fixture. It exists only to exercise the certified product journey without an external LLM provider.",
        )
        claim = ClaimV1(
            claim_id=f"demo-claim-{run_id}",
            statement=f"The planned topic is {plan.canonical_topic}.",
            category=ClaimCategory.EXPERIENCE,
            confidence=ClaimConfidence.HIGH,
            evidence_refs=(evidence.evidence_id,),
            publishability=ClaimPublishability.ALLOWED,
        )
        artifact = ResearchPackV1(
            research_id=f"demo-research-{run_id}",
            plan_id=plan.plan_id,
            verdict=ResearchVerdict.GO,
            key_points=(plan.angle, plan.target_effect),
            claims=(claim,),
            evidence=(evidence,),
            uncertainties=(),
            safety_notes=("Deterministic local demo output; not a factual external-source claim.",),
            forbidden_claims=(),
            recommended_angle=plan.angle,
        )
        input_digest = canonical_sha256({"plan": plan.model_dump(mode="json"), "profile": profile.snapshot()})
        return AgentInvocationResult(artifact=artifact, attempts=(_attempt(AgentKind.RESEARCH, input_digest, artifact),))


class DemoWriterAgent:
    async def write(self, *, tenant_id, run_id, plan, profile, research):
        claim_id = research.claims[0].claim_id
        topic = plan.canonical_topic.replace(".", " ")
        title = f"{topic.title()} · demo verificable"
        hook = f"Una forma clara de pensar {topic}: {plan.angle}."
        body = (
            f"Este contenido fue producido por el modo demo determinista de prodAgentic para validar el journey R2. "
            f"Objetivo: {plan.target_effect}. La identidad, el plan, QA y los artefactos siguen siendo autoridad real y persistente."
        )
        cta = "Revísalo, apruébalo y comprueba que el estado persiste."
        if plan.format == "text":
            format_spec = TextFormatSpecV1()
        elif plan.format == "single_image":
            format_spec = SingleImageSpecV1(
                headline=title,
                supporting_copy=(plan.angle, plan.target_effect),
                footer="prodAgentic · R2 demo",
            )
        elif plan.format == "carousel":
            format_spec = CarouselSpecV1(slides=(
                CarouselSlideV1(slide_id="01", role="hook", headline=title, body=hook),
                CarouselSlideV1(slide_id="02", role="explain", headline="Qué está validando", body=body),
                CarouselSlideV1(slide_id="03", role="takeaway", headline="Siguiente decisión", body=cta),
            ))
        elif plan.format == "infographic":
            format_spec = InfographicSpecV1(
                title=title,
                sections=(
                    InfographicSectionV1(section_id="goal", label="Objetivo", value_or_copy=plan.target_effect),
                    InfographicSectionV1(section_id="angle", label="Ángulo", value_or_copy=plan.angle),
                    InfographicSectionV1(section_id="state", label="Estado", value_or_copy="Plan → producción → QA → Review", relationship="Flujo gobernado"),
                ),
            )
        else:
            raise ValueError(f"Unsupported demo format: {plan.format}")
        artifact = ContentSpecV1(
            content_spec_id=f"demo-content-{run_id}",
            plan_id=plan.plan_id,
            language=profile.copy_policy.target_language,
            title=title,
            hook=hook,
            body=body,
            cta=cta,
            hashtags=("#prodAgentic", "#R2Demo"),
            alt_text_draft=f"Visual demo about {topic}" if plan.format != "text" else None,
            format=plan.format,
            format_spec=format_spec,
            claims_used=(claim_id,),
        )
        input_digest = canonical_sha256({
            "plan": plan.model_dump(mode="json"),
            "profile": profile.snapshot(),
            "research": research.model_dump(mode="json"),
        })
        return AgentInvocationResult(artifact=artifact, attempts=(_attempt(AgentKind.WRITER, input_digest, artifact),))


class DemoEditorAgent:
    async def edit(self, *, tenant_id, run_id, plan, profile, research, content, revision_cycle):
        artifact = EditorialReviewV1(
            review_id=f"demo-review-{run_id}-{revision_cycle}",
            verdict=EditorialVerdict.APPROVE_TEXT,
            brand_match=EditorialCheck.PASS,
            clarity=EditorialCheck.PASS,
            hook_strength=EditorialCheck.PASS,
            factual_consistency=EditorialCheck.PASS,
            platform_fit=EditorialCheck.PASS,
            issues=(),
            revised_content_spec=None,
        )
        input_digest = canonical_sha256({
            "plan": plan.model_dump(mode="json"),
            "profile": profile.snapshot(),
            "research": research.model_dump(mode="json"),
            "content": content.model_dump(mode="json"),
            "revision_cycle": revision_cycle,
        })
        return AgentInvocationResult(artifact=artifact, attempts=(_attempt(AgentKind.EDITOR, input_digest, artifact),))


def build_demo_s3_service(repository) -> StructuredAgentCellService:
    return StructuredAgentCellService(
        repository=repository,
        research_agent=DemoResearchAgent(),
        writer_agent=DemoWriterAgent(),
        editor_agent=DemoEditorAgent(),
    )
