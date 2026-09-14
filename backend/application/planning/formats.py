from __future__ import annotations

import hashlib

from domain.planning.models import BatchRequestConstraints, IdeaCandidateV1, TargetWindow
from domain.profiles.models import ProfileVersion

R4_AUTO_FORMAT_POLICY_VERSION = "r4-auto-format-v1"
_VISUAL_FORMATS = ("carousel", "infographic", "single_image")
_VISUAL_FIRST_TRAITS = {
    "technical", "tecnico", "técnico", "data", "datos", "detailed", "detallado",
    "analytical", "analitico", "analítico", "bold", "energetic", "energetico",
    "energético", "aggressive", "agresivo", "impactful", "potente", "dark", "oscuro",
    "premium",
}
_VISUAL_FIRST_CHANNELS = {"instagram", "tiktok"}


def profile_is_visual_first(profile: ProfileVersion, constraints: BatchRequestConstraints) -> bool:
    """Derive visual-first policy only from frozen Profile/request authority.

    `clean` alone is deliberately not enough because R3 used it as a neutral
    fallback. No vertical/account-name rules are allowed here.
    """
    if constraints.desired_format is not None:
        return constraints.desired_format != "text"
    channels = {item.value for item in profile.publishing_preferences.channels}
    if channels & _VISUAL_FIRST_CHANNELS:
        return True
    traits = {item.strip().lower() for item in profile.visual_system.traits}
    if traits & _VISUAL_FIRST_TRAITS:
        return True
    emphasis = (constraints.channel_emphasis or "").strip().lower()
    return any(token in emphasis for token in ("visual", "carousel", "image", "imagen", "infographic", "infografia", "infografía"))


def _best_visual_format(candidate: IdeaCandidateV1, ordinal: int) -> str:
    if candidate.hook_pattern == "diagram_flow":
        return "infographic"
    if candidate.hook_pattern in {"numbered", "story", "myth_vs_fact"}:
        return "carousel"
    if candidate.target_effect in {"understanding", "better_decision"}:
        return "infographic" if ordinal % 2 else "carousel"
    if candidate.hook_pattern == "counterintuitive":
        return "single_image"
    return _VISUAL_FORMATS[ordinal % len(_VISUAL_FORMATS)]


def apply_auto_format_policy(
    profile: ProfileVersion,
    constraints: BatchRequestConstraints,
    candidates: list[IdeaCandidateV1],
) -> list[IdeaCandidateV1]:
    """Freeze auto-format decisions before novelty/diversity selection.

    Explicit `desired_format` always wins. Otherwise visual-first Profiles convert
    text proposals into a governed visual medium. Changed candidate IDs are
    re-derived so candidate identity includes the policy and final format.
    """
    if constraints.desired_format is not None:
        return candidates
    if not profile_is_visual_first(profile, constraints):
        return candidates

    resolved: list[IdeaCandidateV1] = []
    for ordinal, candidate in enumerate(candidates):
        if candidate.tentative_format != "text":
            resolved.append(candidate)
            continue
        final_format = _best_visual_format(candidate, ordinal)
        material = "|".join((candidate.candidate_id, R4_AUTO_FORMAT_POLICY_VERSION, final_format))
        resolved.append(
            candidate.model_copy(
                update={
                    "candidate_id": f"cand-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}",
                    "tentative_format": final_format,
                    "rationale": (
                        f"{candidate.rationale}; {R4_AUTO_FORMAT_POLICY_VERSION} resolved text proposal "
                        f"to {final_format} because frozen Profile/request authority is visual-first"
                    )[:600],
                }
            )
        )
    return resolved


class AutoFormatCandidateSource:
    """Planner source decorator that makes the format decision part of authority."""

    def __init__(self, inner):
        self.inner = inner

    def generate(
        self,
        profile: ProfileVersion,
        target_window: TargetWindow,
        constraints: BatchRequestConstraints,
        target_pool_size: int,
    ) -> list[IdeaCandidateV1]:
        candidates = self.inner.generate(profile, target_window, constraints, target_pool_size)
        return apply_auto_format_policy(profile, constraints, candidates)
