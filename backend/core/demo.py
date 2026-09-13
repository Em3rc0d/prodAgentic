from __future__ import annotations

import os
from uuid import uuid4

from application.content_quality.policy import evaluate_publishability
from application.production.service import StructuredAgentCellService
from domain.planning.models import canonicalize_topic
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    CarouselSlideV1,
    CarouselSpecV1,
    ContentSpecV1,
    EditorialCheck,
    EditorialIssueSeverity,
    EditorialReviewV1,
    EditorialVerdict,
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
        prompt_version="mk1-r3-demo-v1",
        provider="deterministic-demo",
        model="fixture-v2",
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


def _topic(plan, profile) -> str:
    for candidate in profile.editorial_strategy.topic_families:
        if canonicalize_topic(candidate) == plan.canonical_topic:
            return candidate.strip()
    if plan.subtopics:
        return plan.subtopics[0].strip()
    value = plan.canonical_topic.replace(".", " ").replace("_", " ").strip()
    words = value.split()
    if len(words) > 8:
        # Old Profiles can contain an entire audience sentence as a topic. Keep
        # the demo readable without inventing vocabulary; new R3 Profiles derive
        # compact topic families before planning.
        value = " ".join(words[:8])
    return value or profile.identity.name


def _angle_label(angle: str, language: str) -> str:
    labels = {
        "es": {
            "common situation": "una situación cotidiana",
            "personal realization": "una conclusión práctica",
            "unexpected friction": "la fricción que suele pasar desapercibida",
            "how it works": "cómo funciona",
            "practical checklist": "un checklist práctico",
            "myth correction": "corregir una idea común",
            "worked example": "un ejemplo aplicado",
            "tradeoff": "el trade-off real",
            "counterintuitive lesson": "una lección contraintuitiva",
            "decision framework": "un marco de decisión",
            "problem to outcome": "del problema al resultado",
            "use case": "un caso de uso",
            "decision guide": "una guía de decisión",
            "question to peers": "una pregunta útil a la comunidad",
            "shared experience": "una experiencia compartida",
            "opinion prompt": "un contraste de opiniones",
            "recognizable moment": "un momento reconocible",
            "expectation vs reality": "expectativa vs. realidad",
            "light observation": "una observación ligera",
        },
        "en": {},
        "pt": {},
    }
    if language == "es":
        return labels["es"].get(angle, angle.replace("_", " "))
    return angle.replace("_", " ")


def _copy_pack(*, subject: str, role: str, angle: str, language: str) -> dict[str, object]:
    role = role.strip().lower()
    if language == "en":
        hooks = {
            "relatable": f"Is {subject} becoming bigger than it needs to be? Reduce it to one decision.",
            "education": f"To make progress with {subject}, start with one decision instead of an endless list.",
            "insight": f"More information about {subject} is useless if it does not change the decision.",
            "value": f"Before spending more time on {subject}, define the outcome you actually need.",
            "community": f"If you could improve only one thing about {subject}, what would you choose first?",
            "humor": f"Plan: solve one {subject} question. Reality: fourteen tabs open.",
        }
        body = (
            f"Use {angle} as a filter: define the decision, remove what does not change it, "
            "and finish with one next action you can verify. The goal is not to cover more; it is to leave with clearer judgment."
        )
        cta = "What criterion would you use for the next decision?"
        steps = ("Define the decision", "Remove the noise", "Choose one next action")
        labels = ("Decision", "Filter", "Next step")
    elif language == "pt":
        hooks = {
            "relatable": f"{subject} ficou maior do que precisava? Reduza o problema a uma decisão.",
            "education": f"Para avançar em {subject}, comece por uma decisão, não por uma lista infinita.",
            "insight": f"Mais informação sobre {subject} não ajuda se não muda a decisão.",
            "value": f"Antes de investir mais tempo em {subject}, defina o resultado que realmente precisa.",
            "community": f"Se pudesse melhorar só uma coisa em {subject}, o que escolheria primeiro?",
            "humor": f"Plano: resolver uma dúvida de {subject}. Realidade: catorze abas abertas.",
        }
        body = (
            f"Use {angle} como filtro: defina a decisão, elimine o que não muda essa decisão "
            "e termine com uma próxima ação verificável. O objetivo não é cobrir mais; é sair com mais critério."
        )
        cta = "Qual critério você usaria na próxima decisão?"
        steps = ("Defina a decisão", "Elimine o ruído", "Escolha a próxima ação")
        labels = ("Decisão", "Filtro", "Próximo passo")
    else:
        hooks = {
            "relatable": f"¿{subject} se está haciendo más grande de lo necesario? Reduce el problema a una sola decisión.",
            "education": f"Para avanzar con {subject}, empieza por una decisión concreta, no por una lista infinita.",
            "insight": f"Más información sobre {subject} no sirve si no cambia tu decisión.",
            "value": f"Antes de invertir más tiempo en {subject}, define qué resultado realmente necesitas.",
            "community": f"Si solo pudieras mejorar una cosa de {subject}, ¿qué elegirías primero?",
            "humor": f"Plan: resolver una duda de {subject}. Realidad: catorce pestañas abiertas.",
        }
        body = (
            f"Usa {angle} como filtro: define la decisión, elimina lo que no cambia esa decisión "
            "y termina con una siguiente acción que puedas comprobar. El objetivo no es cubrir más; es salir con mejor criterio."
        )
        cta = "¿Qué criterio usarías tú para la siguiente decisión?"
        steps = ("Define la decisión", "Reduce el ruido", "Elige un siguiente paso")
        labels = ("Decisión", "Filtro", "Siguiente paso")

    hook = hooks.get(role, hooks["education"])
    return {"hook": hook, "body": body, "cta": cta, "steps": steps, "labels": labels}


class DemoResearchAgent:
    async def research(self, *, tenant_id, run_id, plan, profile):
        artifact = ResearchPackV1(
            research_id=f"demo-research-{run_id}",
            plan_id=plan.plan_id,
            verdict=ResearchVerdict.GO,
            key_points=(plan.angle, plan.target_effect),
            claims=(),
            evidence=(),
            uncertainties=(),
            safety_notes=(
                "Provider-free local fixture: copy must remain interpretive/educational and must not fabricate external facts, metrics or personal experience.",
            ),
            forbidden_claims=(),
            recommended_angle=plan.angle,
        )
        input_digest = canonical_sha256({"plan": plan.model_dump(mode="json"), "profile": profile.snapshot()})
        return AgentInvocationResult(artifact=artifact, attempts=(_attempt(AgentKind.RESEARCH, input_digest, artifact),))


class DemoWriterAgent:
    async def write(self, *, tenant_id, run_id, plan, profile, research):
        language = profile.copy_policy.target_language
        subject = _topic(plan, profile)
        angle = _angle_label(plan.angle, language)
        copy = _copy_pack(subject=subject, role=plan.role, angle=angle, language=language)
        hook = str(copy["hook"])
        body = str(copy["body"])
        cta = str(copy["cta"])
        steps = tuple(str(item) for item in copy["steps"])
        labels = tuple(str(item) for item in copy["labels"])
        title = hook.rstrip(".?")

        if plan.format == "text":
            format_spec = TextFormatSpecV1()
        elif plan.format == "single_image":
            format_spec = SingleImageSpecV1(
                headline=title[:120],
                supporting_copy=steps,
                footer=profile.identity.name,
            )
        elif plan.format == "carousel":
            if language == "en":
                slide_titles = (title, "What is the decision?", "Remove the noise", "Try one next step", "Keep this idea")
            elif language == "pt":
                slide_titles = (title, "Qual é a decisão?", "Elimine o ruído", "Teste um próximo passo", "Leve esta ideia")
            else:
                slide_titles = (title, "¿Cuál es la decisión?", "Reduce el ruido", "Prueba un siguiente paso", "Quédate con esta idea")
            format_spec = CarouselSpecV1(
                slides=(
                    CarouselSlideV1(slide_id="01", role="hook", headline=slide_titles[0], body=None),
                    CarouselSlideV1(slide_id="02", role="explain", headline=slide_titles[1], body=body),
                    CarouselSlideV1(slide_id="03", role="example", headline=slide_titles[2], bullets=steps[:2]),
                    CarouselSlideV1(slide_id="04", role="takeaway", headline=slide_titles[3], body=steps[2]),
                    CarouselSlideV1(slide_id="05", role="cta", headline=slide_titles[4], body=cta),
                )
            )
        elif plan.format == "infographic":
            format_spec = InfographicSpecV1(
                title=title[:120],
                sections=tuple(
                    InfographicSectionV1(
                        section_id=f"step-{index + 1}",
                        label=labels[index],
                        value_or_copy=steps[index],
                        relationship="→" if index < len(steps) - 1 else None,
                    )
                    for index in range(len(steps))
                ),
            )
        else:
            raise ValueError(f"Unsupported demo format: {plan.format}")

        artifact = ContentSpecV1(
            content_spec_id=f"demo-content-{run_id}",
            plan_id=plan.plan_id,
            language=language,
            title=title,
            hook=hook,
            body=body,
            cta=cta,
            hashtags=(),
            alt_text_draft=(
                f"Editorial visual about {subject} organized as a practical decision framework."
                if plan.format != "text"
                else None
            ),
            format=plan.format,
            format_spec=format_spec,
            claims_used=(),
        )
        input_digest = canonical_sha256({
            "plan": plan.model_dump(mode="json"),
            "profile": profile.snapshot(),
            "research": research.model_dump(mode="json"),
        })
        return AgentInvocationResult(artifact=artifact, attempts=(_attempt(AgentKind.WRITER, input_digest, artifact),))


class DemoEditorAgent:
    async def edit(self, *, tenant_id, run_id, plan, profile, research, content, revision_cycle):
        issues = evaluate_publishability(content=content, plan=plan, profile=profile)
        blocking = tuple(issue for issue in issues if issue.severity == EditorialIssueSeverity.BLOCKING)
        hook_warn = any(issue.code.startswith("copy.generic_hook") or issue.code.startswith("copy.hook") for issue in issues)
        platform_warn = any(issue.code.startswith("visual.") for issue in issues)
        artifact = EditorialReviewV1(
            review_id=f"demo-review-{run_id}-{revision_cycle}",
            verdict=EditorialVerdict.REJECT if blocking else EditorialVerdict.APPROVE_TEXT,
            brand_match=EditorialCheck.PASS,
            clarity=EditorialCheck.PASS,
            hook_strength=EditorialCheck.WARN if hook_warn else EditorialCheck.PASS,
            factual_consistency=EditorialCheck.PASS,
            platform_fit=EditorialCheck.WARN if platform_warn else EditorialCheck.PASS,
            issues=issues,
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
