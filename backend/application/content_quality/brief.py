from __future__ import annotations

from domain.planning.models import ContentPlanV1
from domain.profiles.models import Goal, ProfileVersion


_GOAL_GUIDANCE: dict[Goal, str] = {
    Goal.GROW: "Earn attention with a specific, immediately relevant promise and a reason to share or save.",
    Goal.EDUCATE: "Teach one useful decision, model, procedure or distinction that the audience can apply.",
    Goal.BUILD_AUTHORITY: "Demonstrate judgment and domain understanding without unsupported claims or empty expertise signals.",
    Goal.SELL: "Connect a real audience problem to a clear value proposition without pressure, fabricated proof or unsupported outcomes.",
    Goal.BUILD_COMMUNITY: "Invite a meaningful response, comparison, choice or shared experience instead of engagement bait.",
    Goal.ENTERTAIN: "Deliver a recognizable emotional payoff while preserving the Profile voice and topic authority.",
}

_CHANNEL_GUIDANCE = {
    "linkedin": "Professional feed: make the first lines carry the thesis; favor concrete insight, proof, decisions and skimmable structure.",
    "instagram": "Visual feed: make the visual artifact understandable before the caption; favor save/share value and strong hierarchy.",
    "tiktok": "Fast feed: the first beat must communicate tension, surprise, utility or identification without setup-heavy prose.",
    "manual_export": "Channel-neutral package: preserve the core idea and keep copy adaptable without leaking internal workflow metadata.",
}

_ROLE_GUIDANCE = {
    "education": "Teach one useful thing with a concrete takeaway, worked example, checklist, comparison or decision rule.",
    "educational": "Teach one useful thing with a concrete takeaway, worked example, checklist, comparison or decision rule.",
    "relatable": "Start from a recognizable situation, tension or frustration and turn it into a useful insight.",
    "story": "Use a clear setup -> tension -> lesson arc without inventing personal experience not present in evidence.",
    "personal": "Use first-person perspective only when the frozen evidence/profile authorizes that experience; otherwise preserve a neutral viewpoint.",
    "community": "Create a real decision, trade-off or discussion prompt that gives the audience something substantive to respond to.",
    "insight": "Surface a non-obvious distinction or implication and make the reasoning explicit.",
    "proof": "Lead with verifiable evidence or a concrete demonstration; never fabricate metrics, customers or outcomes.",
    "offer": "Explain value through the audience problem, mechanism and fit; avoid generic promotional filler.",
}


def build_creative_brief(*, plan: ContentPlanV1, profile: ProfileVersion) -> dict:
    """Derive a provider-neutral creative brief from frozen product authority.

    The brief is intentionally deterministic and contains no vertical-specific
    business logic. Client specialization comes only from ProfileVersion,
    ContentPlanV1 and their already-governed fields.
    """

    role_key = plan.role.strip().lower()
    role_guidance = _ROLE_GUIDANCE.get(
        role_key,
        "Make the planned role obvious in the finished piece and give the audience a concrete reason to care.",
    )
    goals = [goal.value for goal in profile.goals]
    goal_guidance = [_GOAL_GUIDANCE[goal] for goal in profile.goals]
    channels = [channel.value for channel in profile.publishing_preferences.channels]

    return {
        "brief_version": "mk1-r3-creative-brief-v1",
        "identity": {
            "name": profile.identity.name,
            "account_type": profile.identity.account_type.value,
            "summary": profile.identity.summary,
        },
        "audience": list(profile.audience),
        "goals": goals,
        "goal_guidance": goal_guidance,
        "editorial_role": plan.role,
        "role_guidance": role_guidance,
        "topic": plan.canonical_topic,
        "subtopics": list(plan.subtopics),
        "angle": plan.angle,
        "target_effect": plan.target_effect,
        "hook_pattern": plan.hook_pattern,
        "format": plan.format,
        "voice": {
            "traits": list(profile.copy_policy.voice_traits),
            "nuance": profile.copy_policy.nuance,
            "hook_tendencies": list(profile.copy_policy.hook_tendencies),
            "cta_style": profile.copy_policy.cta_style,
            "caption_length_tendency": profile.copy_policy.caption_length_tendency,
        },
        "visual_traits": list(profile.visual_system.traits),
        "channels": channels,
        "channel_guidance": [_CHANNEL_GUIDANCE[channel] for channel in channels if channel in _CHANNEL_GUIDANCE],
        "quality_bar": [
            "The piece must read like finished audience-facing content, never like test output, telemetry, a prompt, a schema or an internal workflow trace.",
            "Prefer specificity over generic claims: use the exact audience problem, angle, decision, example or tension available in authority.",
            "The hook must create immediate relevance without clickbait that the body does not repay.",
            "Every section must earn its place; remove filler, throat-clearing and repeated restatements.",
            "Do not expose taxonomy IDs, snake_case target labels, state names, digests, QA language or implementation terminology.",
            "Respect the planned role and format while varying structure naturally across pieces; do not force one template across all clients.",
            "Keep factual and experience claims inside the ResearchPack boundary.",
            "A visual format must have concise on-canvas copy with enough semantic contrast between pages/sections to justify the format.",
        ],
    }
