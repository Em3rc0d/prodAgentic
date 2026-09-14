from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.router import AttemptCompleted, AttemptStarted, ContentChunk, ModelExecutionRequest, RoutingExhausted
from core.context import GenerationContext, LanguageCode
from core.model_registry import ModelProfile
from core.validator import ArtifactType
from domain.planning.models import BatchRequestConstraints, ClaimRisk, IdeaCandidateV1, TargetWindow, canonicalize_topic
from domain.profiles.models import ProfileVersion


class CandidateGenerationError(RuntimeError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _IdeaDraft(_StrictModel):
    role: Literal["relatable", "education", "insight", "value", "community", "humor"]
    topic: str = Field(min_length=2, max_length=160)
    subtopics: tuple[str, ...] = Field(default=(), max_length=8)
    angle: str = Field(min_length=2, max_length=200)
    hook_pattern: Literal["question", "counterintuitive", "numbered", "story", "myth_vs_fact", "diagram_flow"]
    target_effect: Literal["recognition", "understanding", "better_decision", "consideration", "conversation", "engagement"]
    tentative_format: Literal["text", "single_image", "carousel", "infographic"]
    rationale: str = Field(min_length=8, max_length=500)
    claim_risk: ClaimRisk = ClaimRisk.LOW


class _IdeaPool(_StrictModel):
    ideas: tuple[_IdeaDraft, ...] = Field(min_length=1, max_length=24)


class RouterCandidateSource:
    """R4 creative candidate source backed by the governed ModelRouter.

    The model proposes creative candidates only. Hard novelty, cooldown, current-batch
    diversity, ProfileVersion freezing and final selection remain deterministic in
    BatchPlannerService. Model output is strict JSON and candidate IDs are derived
    locally, so provider text can never become planning identity authority.
    """

    prompt_version = "mk1-r4-candidate-source-v1"

    def __init__(self, router, *, max_contract_repairs: int = 1):
        self.router = router
        self.max_contract_repairs = max(0, min(max_contract_repairs, 1))

    async def generate(
        self,
        profile: ProfileVersion,
        target_window: TargetWindow,
        constraints: BatchRequestConstraints,
        target_pool_size: int,
    ) -> list[IdeaCandidateV1]:
        if target_pool_size < 1 or target_pool_size > 24:
            raise ValueError("target_pool_size must be between 1 and 24")

        language = LanguageCode(profile.copy_policy.target_language)
        context = GenerationContext(
            run_id=f"planning-{uuid4()}",
            topic=", ".join(profile.editorial_strategy.topic_families[:6]) or profile.identity.summary,
            style="creative-planning",
            requested_source_language=LanguageCode.AUTO,
            detected_source_language=LanguageCode.UNKNOWN,
            source_detection_confidence=0.0,
            requested_target_language=language,
            resolved_target_language=language,
            image_prompt_language=language,
            audience="; ".join(profile.audience),
            content_profile_id=profile.profile_id,
            content_profile_snapshot=None,
        )

        schema = _IdeaPool.model_json_schema()
        payload = {
            "profile": {
                "identity": profile.identity.model_dump(mode="json"),
                "goals": [item.value for item in profile.goals],
                "audience": list(profile.audience),
                "topic_families": list(profile.editorial_strategy.topic_families),
                "excluded_topics": list(profile.editorial_strategy.excluded_topics),
                "voice": list(profile.copy_policy.voice_traits),
                "voice_nuance": profile.copy_policy.nuance,
                "channels": [item.value for item in profile.publishing_preferences.channels],
            },
            "target_window": target_window.model_dump(mode="json"),
            "constraints": constraints.model_dump(mode="json"),
            "requested_pool_size": target_pool_size,
        }
        system = (
            "You are prodAgentic R4 Editorial Strategist. Generate a candidate pool for one real client Profile. "
            "Do not write finished posts. Propose specific publishable concepts that a strong human content strategist would consider. "
            "Every idea must be materially different in topic/angle/payoff, not a wording variation. Use natural audience-facing topics, never copy an entire audience sentence into topic. "
            "Respect explicit goals, channels, voice, include/avoid topics and desired_format. If desired_format is null, prefer visual formats for ideas whose value is visual and text only when text is genuinely the best medium. "
            "Do not invent facts, studies, metrics, customers, credentials, results or personal experiences; later Research owns factual support. "
            "rationale must explain why this concept fits this Profile and audience. Return only the requested JSON object."
        )
        base_prompt = (
            f"Return exactly one JSON object matching this schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n\n"
            f"AUTHORITATIVE INPUT:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n\n"
            f"Produce exactly {target_pool_size} ideas."
        )

        feedback = ""
        for repair in range(self.max_contract_repairs + 1):
            prompt = base_prompt
            if feedback:
                prompt += f"\n\nThe previous output failed validation. Return the complete object again. Validation feedback: {feedback[:1200]}"
            raw = await self._invoke(context=context, system=system, prompt=prompt)
            try:
                pool = _IdeaPool.model_validate(json.loads(self._strip_fence(raw)))
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                if repair >= self.max_contract_repairs:
                    raise CandidateGenerationError("Model candidate output remained invalid after bounded repair") from exc
                feedback = str(exc)
                continue

            if len(pool.ideas) != target_pool_size:
                if repair >= self.max_contract_repairs:
                    raise CandidateGenerationError(
                        f"Model candidate pool returned {len(pool.ideas)} ideas; expected {target_pool_size}"
                    )
                feedback = f"ideas must contain exactly {target_pool_size} items; got {len(pool.ideas)}"
                continue
            return self._materialize(profile, target_window, constraints, pool.ideas)

        raise CandidateGenerationError("Model candidate generation exhausted")

    async def _invoke(self, *, context: GenerationContext, system: str, prompt: str) -> str:
        request = ModelExecutionRequest(
            context=context,
            model_profile=ModelProfile.QUALITY_TEXT,
            artifact_type=ArtifactType.IDEAS,
            system_instruction=system,
            user_prompt=prompt,
            expected_output_language=context.resolved_target_language,
        )
        buffers: dict[str, str] = {}
        current: str | None = None
        async for event in self.router.stream_generation(request):
            if isinstance(event, AttemptStarted):
                current = event.attempt_id
                buffers[current] = ""
            elif isinstance(event, ContentChunk) and event.attempt_id == current:
                buffers[current] = buffers.get(current, "") + event.text
            elif isinstance(event, AttemptCompleted):
                value = buffers.get(event.attempt_id, "").strip()
                if value:
                    return value
            elif isinstance(event, RoutingExhausted):
                raise CandidateGenerationError("Model routing exhausted before a valid candidate pool was produced")
        raise CandidateGenerationError("Model routing ended without a completed candidate pool")

    @staticmethod
    def _strip_fence(value: str) -> str:
        stripped = value.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            first_newline = stripped.find("\n")
            if first_newline >= 0:
                stripped = stripped[first_newline + 1 : -3].strip()
        return stripped

    @staticmethod
    def _materialize(
        profile: ProfileVersion,
        target_window: TargetWindow,
        constraints: BatchRequestConstraints,
        drafts: tuple[_IdeaDraft, ...],
    ) -> list[IdeaCandidateV1]:
        allowed_format = constraints.desired_format
        avoid = {canonicalize_topic(item) for item in (*constraints.avoid_topics, *profile.editorial_strategy.excluded_topics)}
        candidates: list[IdeaCandidateV1] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for index, draft in enumerate(drafts):
            topic = " ".join(draft.topic.split()).strip()
            canonical = canonicalize_topic(topic)
            if not canonical or canonical in avoid:
                continue
            tentative_format = allowed_format or draft.tentative_format
            key = (canonical, draft.role, draft.angle.strip().lower(), draft.hook_pattern, tentative_format)
            if key in seen:
                continue
            seen.add(key)
            identity = "|".join(
                (
                    profile.profile_id,
                    str(profile.version),
                    str(index),
                    topic,
                    draft.role,
                    draft.angle,
                    draft.hook_pattern,
                    tentative_format,
                    target_window.start_at.isoformat(),
                )
            )
            candidates.append(
                IdeaCandidateV1(
                    candidate_id=f"cand-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}",
                    role=draft.role,
                    topic=topic,
                    subtopics=tuple(dict.fromkeys(item.strip() for item in draft.subtopics if item.strip())),
                    angle=draft.angle.strip(),
                    hook_pattern=draft.hook_pattern,
                    target_effect=draft.target_effect,
                    tentative_format=tentative_format,
                    rationale=draft.rationale.strip(),
                    claim_risk=draft.claim_risk,
                )
            )
        if not candidates:
            raise CandidateGenerationError("Model candidate pool contained no usable ideas after policy filtering")
        return candidates
