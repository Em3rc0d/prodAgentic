from __future__ import annotations

import hashlib
import json
import re
import uuid

from models.grounding import FactualEnvelope
from models.value_engine import (
    AngleCandidate,
    AngleEngineOutput,
    AngleSelectionSnapshot,
    AttentionCriticAssessment,
    ContentQualityDecision,
    ContentQualityGate,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_model(value) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json") if hasattr(value, "model_dump") else value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(canonical)


class AngleSelectionPolicy:
    """Deterministically choose editorial framing without granting factual authority."""

    VERSION = "angle-selection-policy-v1"

    @classmethod
    def validate_evidence_refs(
        cls,
        output: AngleEngineOutput,
        factual_envelope: FactualEnvelope | None,
    ) -> None:
        known_statement_ids: set[str] = set()
        if factual_envelope is not None:
            known_statement_ids = {
                item.statement_id
                for item in [
                    *factual_envelope.allowed_facts,
                    *factual_envelope.allowed_inferences,
                ]
            }

        for candidate in output.candidates:
            if factual_envelope is None and candidate.evidence_statement_refs:
                raise ValueError(
                    "angle candidate cannot cite factual-envelope statement refs when no envelope exists"
                )
            unknown = [
                ref
                for ref in candidate.evidence_statement_refs
                if ref not in known_statement_ids
            ]
            if unknown:
                raise ValueError(
                    "angle candidate references unknown factual-envelope statements: "
                    + ", ".join(sorted(unknown))
                )

    @classmethod
    def score(cls, candidate: AngleCandidate) -> float:
        positive = (
            0.24 * candidate.audience_relevance
            + 0.22 * candidate.distinctiveness
            + 0.16 * candidate.specificity
            + 0.23 * candidate.profile_curiosity
            + 0.15 * candidate.evidence_density
        )
        risk_penalty = 0.35 * candidate.spam_risk + 0.45 * candidate.ai_slop_risk
        return max(0.0, min(1.0, positive - risk_penalty))

    @classmethod
    def select(
        cls,
        output: AngleEngineOutput,
        factual_envelope: FactualEnvelope | None,
    ) -> AngleSelectionSnapshot:
        cls.validate_evidence_refs(output, factual_envelope)
        safe = [
            candidate
            for candidate in output.candidates
            if candidate.spam_risk < 0.60 and candidate.ai_slop_risk < 0.60
        ]
        if not safe:
            raise ValueError("all proposed angles exceed editorial spam/AI-slop risk ceiling")

        ranked = sorted(
            safe,
            key=lambda candidate: (
                cls.score(candidate),
                candidate.distinctiveness,
                candidate.profile_curiosity,
                candidate.evidence_density,
                candidate.candidate_id,
            ),
            reverse=True,
        )
        selected = ranked[0]
        alternatives = [candidate for candidate in output.candidates if candidate.candidate_id != selected.candidate_id]
        return AngleSelectionSnapshot(
            selection_id=str(uuid.uuid4()),
            output_id=output.output_id,
            selected_candidate_id=selected.candidate_id,
            selection_policy_version=cls.VERSION,
            selected_score=cls.score(selected),
            selected_candidate=selected,
            alternatives=alternatives,
            idea_sha256=output.idea_sha256,
            research_sha256=output.research_sha256,
            factual_envelope_sha256=output.factual_envelope_sha256,
        )

    @staticmethod
    def render_for_writer(snapshot: AngleSelectionSnapshot) -> str:
        candidate = snapshot.selected_candidate
        refs = ", ".join(candidate.evidence_statement_refs) or "NONE"
        return "\n".join(
            [
                "<ANGLE_STRATEGY_DATA>",
                f"content_family={candidate.content_family.value}",
                f"angle={candidate.angle}",
                f"hook_direction={candidate.hook_direction}",
                f"reader_tension={candidate.reader_tension}",
                f"reader_payoff={candidate.reader_payoff}",
                f"factual_envelope_statement_refs={refs}",
                "AUTHORITY RULE: This block is editorial framing only. It grants no factual permission.",
                "Do not copy any factual detail from this block unless independently permitted by the factual envelope/research and final Grounding.",
                "</ANGLE_STRATEGY_DATA>",
            ]
        )


class ContentQualityPolicy:
    """Deterministic editorial gate. Factual trust is intentionally out-of-band."""

    VERSION = "content-quality-policy-v1"

    _ENGAGEMENT_BAIT = [
        re.compile(r"\bcomment\s+[\"'“”]?\w+", re.IGNORECASE),
        re.compile(r"\bcomenta\s+[\"'“”]?\w+", re.IGNORECASE),
        re.compile(r"\bcomente\s+[\"'“”]?\w+", re.IGNORECASE),
        re.compile(r"\btype\s+[\"'“”]?\w+\s+below\b", re.IGNORECASE),
    ]
    _GENERIC_SLOP = (
        "in today's fast-paced world",
        "in today's rapidly evolving",
        "en el mundo actual",
        "en el vertiginoso mundo",
        "game-changer",
        "paradigm shift",
        "unlock the power",
        "revolutionize the way",
        "nadie está hablando de esto",
        "nobody is talking about this",
        "here's the truth nobody tells you",
        "la verdad que nadie te cuenta",
    )

    @classmethod
    def lexical_flags(cls, content: str) -> list[str]:
        flags: list[str] = []
        lowered = content.lower()
        if any(pattern.search(content) for pattern in cls._ENGAGEMENT_BAIT):
            flags.append("ENGAGEMENT_BAIT")
        if any(phrase in lowered for phrase in cls._GENERIC_SLOP):
            flags.append("GENERIC_AI_SLOP_PHRASE")
        first_nonblank = next((line.strip() for line in content.splitlines() if line.strip()), "")
        if len(first_nonblank) > 220:
            flags.append("HOOK_TOO_LONG")
        return flags

    @classmethod
    def evaluate(
        cls,
        assessment: AttentionCriticAssessment,
        content: str,
    ) -> ContentQualityGate:
        hard_flags = cls.lexical_flags(content)
        reasons: list[str] = []

        if assessment.content_sha256 != sha256_text(content):
            hard_flags.append("STALE_CRITIQUE")
            reasons.append("critic assessment is stale relative to content")
        if assessment.engagement_bait_detected and "ENGAGEMENT_BAIT" not in hard_flags:
            hard_flags.append("ENGAGEMENT_BAIT")
        if assessment.generic_opening_detected:
            hard_flags.append("GENERIC_OPENING")
        if assessment.spam_risk >= 0.35:
            hard_flags.append("SPAM_RISK")
        if assessment.ai_slop_risk >= 0.35:
            hard_flags.append("AI_SLOP_RISK")

        thresholds = {
            "hook": 0.68,
            "idea_clarity": 0.72,
            "novelty": 0.58,
            "specificity": 0.62,
            "credibility_signal": 0.62,
            "payoff": 0.68,
            "human_voice": 0.68,
            "profile_curiosity": 0.58,
        }
        for field, minimum in thresholds.items():
            value = getattr(assessment, field)
            if value < minimum:
                reasons.append(f"{field}={value:.2f} below {minimum:.2f}")

        editorial_score = (
            0.16 * assessment.hook
            + 0.12 * assessment.idea_clarity
            + 0.12 * assessment.novelty
            + 0.11 * assessment.specificity
            + 0.11 * assessment.credibility_signal
            + 0.08 * assessment.narrative_progression
            + 0.12 * assessment.payoff
            + 0.08 * assessment.human_voice
            + 0.04 * assessment.conversation_potential
            + 0.06 * assessment.profile_curiosity
        )
        editorial_score = max(0.0, min(1.0, editorial_score))
        if editorial_score < 0.68:
            reasons.append(f"editorial_score={editorial_score:.2f} below 0.68")

        decision = (
            ContentQualityDecision.REWRITE
            if hard_flags or reasons
            else ContentQualityDecision.PASS
        )
        return ContentQualityGate(
            policy_version=cls.VERSION,
            decision=decision,
            editorial_score=editorial_score,
            hard_flags=list(dict.fromkeys(hard_flags)),
            reasons=reasons,
        )

    @staticmethod
    def render_rewrite_feedback(
        assessment: AttentionCriticAssessment,
        gate: ContentQualityGate,
    ) -> str:
        directives = assessment.rewrite_directives or [
            "Strengthen the opening, specificity, human voice and reader payoff without adding facts."
        ]
        return "\n".join(
            [
                "<QUALITY_REWRITE_DATA>",
                "Decision: REWRITE",
                f"Editorial score: {gate.editorial_score:.3f}",
                "Hard flags: " + (", ".join(gate.hard_flags) or "NONE"),
                "Editorial directives:",
                *[f"- {item}" for item in directives],
                "AUTHORITY RULE: Feedback is editorial only. It is not evidence and cannot authorize new factual claims.",
                "Preserve or reduce factual specificity. Never invent a metric, event, customer, result, quote or causal claim to satisfy feedback.",
                "</QUALITY_REWRITE_DATA>",
            ]
        )
