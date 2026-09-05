from __future__ import annotations

import hashlib

from domain.planning.models import (
    BatchRequestConstraints,
    ClaimRisk,
    IdeaCandidateV1,
    TargetWindow,
    canonicalize_topic,
)
from domain.profiles.models import ProfileVersion


_ROLE_BY_GOAL = {
    "grow": "relatable",
    "educate": "education",
    "build_authority": "insight",
    "sell": "value",
    "build_community": "community",
    "entertain": "humor",
}

_ANGLES_BY_ROLE = {
    "relatable": ("common situation", "personal realization", "unexpected friction"),
    "education": ("how it works", "practical checklist", "myth correction", "worked example"),
    "insight": ("tradeoff", "counterintuitive lesson", "decision framework"),
    "value": ("problem to outcome", "use case", "decision guide"),
    "community": ("question to peers", "shared experience", "opinion prompt"),
    "humor": ("recognizable moment", "expectation vs reality", "light observation"),
}

_HOOKS = ("question", "counterintuitive", "numbered", "story", "myth_vs_fact", "diagram_flow")
_FORMATS = ("text", "single_image", "carousel", "infographic")
_EFFECT_BY_ROLE = {
    "relatable": "recognition",
    "education": "understanding",
    "insight": "better_decision",
    "value": "consideration",
    "community": "conversation",
    "humor": "engagement",
}


class DeterministicCandidateSource:
    """Provider-free bounded S2 candidate generator.

    S2 proves planning policy rather than creative model quality. A later candidate
    adapter may use a model behind CandidateSourcePort, but it must still return
    IdeaCandidateV1 and remain bounded by the planner pool contract.
    """

    def generate(
        self,
        profile: ProfileVersion,
        target_window: TargetWindow,
        constraints: BatchRequestConstraints,
        target_pool_size: int,
    ) -> list[IdeaCandidateV1]:
        if target_pool_size < 1 or target_pool_size > 24:
            raise ValueError("target_pool_size must be between 1 and 24")

        topics = list(constraints.include_topics) + list(profile.editorial_strategy.topic_families)
        if not topics:
            topics = list(profile.audience) or [profile.identity.name]
        avoid = {canonicalize_topic(value) for value in (*constraints.avoid_topics, *profile.editorial_strategy.excluded_topics)}
        topics = [value for value in dict.fromkeys(item.strip() for item in topics if item.strip()) if canonicalize_topic(value) not in avoid]
        if not topics:
            return []

        roles = list(
            dict.fromkeys(
                _ROLE_BY_GOAL.get(goal.value if hasattr(goal, "value") else str(goal), "education")
                for goal in profile.goals
            )
        ) or ["education"]

        formats = (constraints.desired_format,) if constraints.desired_format else _FORMATS
        candidates: list[IdeaCandidateV1] = []
        cursor = 0
        while len(candidates) < target_pool_size:
            role = roles[cursor % len(roles)]
            angles = _ANGLES_BY_ROLE.get(role, _ANGLES_BY_ROLE["education"])
            topic = topics[(cursor // max(1, len(angles))) % len(topics)]
            angle = angles[cursor % len(angles)]
            hook = _HOOKS[cursor % len(_HOOKS)]
            tentative_format = formats[cursor % len(formats)]
            target_effect = _EFFECT_BY_ROLE.get(role, "understanding")
            identity = "|".join(
                [
                    profile.profile_id,
                    str(profile.version),
                    str(cursor),
                    topic,
                    role,
                    angle,
                    hook,
                    tentative_format,
                    target_window.start_at.isoformat(),
                ]
            )
            candidate_id = f"cand-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
            rationale_bits = [f"{role} role", f"{angle} angle", f"{hook} hook"]
            if constraints.campaign_goal:
                rationale_bits.append(f"campaign: {constraints.campaign_goal}")
            candidates.append(
                IdeaCandidateV1(
                    candidate_id=candidate_id,
                    role=role,
                    topic=topic,
                    subtopics=(),
                    angle=angle,
                    hook_pattern=hook,
                    target_effect=target_effect,
                    tentative_format=tentative_format,
                    rationale="; ".join(rationale_bits),
                    claim_risk=ClaimRisk.LOW,
                )
            )
            cursor += 1

            # The identity matrix can cycle when a tiny Profile has only one role,
            # one topic and a forced format. Stop rather than emitting duplicates.
            if cursor > 96:
                break

        unique: dict[tuple[str, str, str, str, str], IdeaCandidateV1] = {}
        for item in candidates:
            key = (canonicalize_topic(item.topic), item.role, item.angle, item.hook_pattern, item.tentative_format)
            unique.setdefault(key, item)
        return list(unique.values())[:target_pool_size]
