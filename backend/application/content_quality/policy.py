from __future__ import annotations

import re

from domain.planning.models import ContentPlanV1, normalize_text
from domain.profiles.models import ProfileVersion
from domain.production.models import (
    CarouselSpecV1,
    ContentSpecV1,
    EditorialIssueSeverity,
    EditorialIssueV1,
    InfographicSpecV1,
    SingleImageSpecV1,
)


_INTERNAL_OUTPUT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("internal.demo_mode", re.compile(r"\bmodo demo determinista\b", re.IGNORECASE)),
    ("internal.demo_verification", re.compile(r"\bdemo verificable\b", re.IGNORECASE)),
    ("internal.r2_demo", re.compile(r"\bR2\s+demo\b", re.IGNORECASE)),
    ("internal.journey", re.compile(r"\bvalidar (?:el )?journey\b", re.IGNORECASE)),
    ("internal.profile_version", re.compile(r"\bProfileVersion\b", re.IGNORECASE)),
    ("internal.content_spec", re.compile(r"\bContentSpec(?:V\d+)?\b", re.IGNORECASE)),
    ("internal.visual_spec", re.compile(r"\bVisualSpec(?:V\d+)?\b", re.IGNORECASE)),
    ("internal.qa_artifacts", re.compile(r"\bQA y (?:los )?artefactos\b", re.IGNORECASE)),
    ("internal.state_name", re.compile(r"\b(?:READY_FOR_REVIEW|QA_PENDING|VISUAL_PLANNING)\b")),
)

# These values belong to prodAgentic's own planning/authority vocabulary. We do
# not reject arbitrary snake_case because developer, data and engineering clients
# may legitimately publish code identifiers such as retry_count or user_id.
_INTERNAL_CONTROL_TOKENS = {
    "better_decision",
    "profile_snapshot_digest",
    "content_spec_id",
    "visual_spec_id",
    "qa_report_id",
    "render_input_digest",
    "agent_run_id",
}

_GENERIC_OPENERS = (
    "una forma clara de pensar",
    "en este post",
    "hoy vamos a hablar de",
    "descubre todo sobre",
    "aprende todo sobre",
)

_SNAKE_CASE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def _issue(code: str, severity: EditorialIssueSeverity, message: str, target_ref: str | None = None) -> EditorialIssueV1:
    return EditorialIssueV1(code=code, severity=severity, message=message, target_ref=target_ref)


def _visible_text(content: ContentSpecV1) -> str:
    chunks: list[str] = [content.title or "", content.hook, content.body, content.cta or ""]
    spec = content.format_spec
    if isinstance(spec, SingleImageSpecV1):
        chunks.extend([spec.headline, *spec.supporting_copy, spec.footer or ""])
    elif isinstance(spec, CarouselSpecV1):
        for slide in spec.slides:
            chunks.extend([slide.headline, slide.body or "", *slide.bullets])
    elif isinstance(spec, InfographicSpecV1):
        chunks.append(spec.title)
        for section in spec.sections:
            chunks.extend([section.label, section.value_or_copy, section.relationship or ""])
    return "\n".join(chunk for chunk in chunks if chunk)


def evaluate_publishability(
    *,
    content: ContentSpecV1,
    plan: ContentPlanV1,
    profile: ProfileVersion,
) -> tuple[EditorialIssueV1, ...]:
    """Deterministic floor for audience-facing quality.

    This does not pretend to replace model/human editorial judgment. It blocks
    machine-internal leakage and structurally weak artifacts that should never be
    approved, while returning warnings for softer quality risks. The rules are
    vertical-neutral and bind only to frozen Profile/Plan/Content authority.
    """

    issues: list[EditorialIssueV1] = []
    visible = _visible_text(content)
    normalized_visible = normalize_text(visible)

    for code, pattern in _INTERNAL_OUTPUT_PATTERNS:
        if pattern.search(visible):
            issues.append(
                _issue(
                    code,
                    EditorialIssueSeverity.BLOCKING,
                    "Audience-facing copy exposes internal test, schema, workflow or state terminology.",
                    content.content_spec_id,
                )
            )

    snake_tokens = tuple(dict.fromkeys(_SNAKE_CASE.findall(visible)))
    leaked_control_tokens = tuple(token for token in snake_tokens if token.lower() in _INTERNAL_CONTROL_TOKENS)
    if leaked_control_tokens:
        issues.append(
            _issue(
                "copy.internal_token_leak",
                EditorialIssueSeverity.BLOCKING,
                f"Audience-facing copy exposes prodAgentic control tokens: {', '.join(leaked_control_tokens[:4])}",
                content.content_spec_id,
            )
        )

    canonical_topic = plan.canonical_topic.strip().lower()
    if "." in canonical_topic and canonical_topic in visible.lower():
        issues.append(
            _issue(
                "copy.taxonomy_leak",
                EditorialIssueSeverity.BLOCKING,
                "Audience-facing copy exposes the internal canonical topic taxonomy instead of natural language.",
                content.content_spec_id,
            )
        )

    hook_normalized = normalize_text(content.hook)
    if any(hook_normalized.startswith(normalize_text(prefix)) for prefix in _GENERIC_OPENERS):
        issues.append(
            _issue(
                "copy.generic_hook",
                EditorialIssueSeverity.WARNING,
                "Hook starts with generic framing instead of the Profile audience's specific tension, payoff or decision.",
                "hook",
            )
        )

    if len(content.hook.strip()) > 280:
        issues.append(
            _issue(
                "copy.hook_too_long",
                EditorialIssueSeverity.WARNING,
                "Hook is too long to create fast feed comprehension.",
                "hook",
            )
        )

    if content.title and normalize_text(content.title) == hook_normalized:
        issues.append(
            _issue(
                "copy.title_hook_duplicate",
                EditorialIssueSeverity.WARNING,
                "Title and hook repeat the same sentence instead of creating progression.",
                "title",
            )
        )

    body_normalized = normalize_text(content.body)
    if body_normalized == hook_normalized:
        issues.append(
            _issue(
                "copy.body_hook_duplicate",
                EditorialIssueSeverity.BLOCKING,
                "Body only repeats the hook and delivers no additional value.",
                "body",
            )
        )

    if len(body_normalized.split()) < 12:
        issues.append(
            _issue(
                "copy.value_density_low",
                EditorialIssueSeverity.WARNING,
                "Body is very short relative to the promised idea; confirm that the format itself carries enough value.",
                "body",
            )
        )

    if content.cta and normalize_text(content.cta) in {"comenta", "comparte", "guardalo", "dale like"}:
        issues.append(
            _issue(
                "copy.engagement_bait_cta",
                EditorialIssueSeverity.WARNING,
                "CTA is generic engagement bait; prefer a useful next action or substantive discussion prompt.",
                "cta",
            )
        )

    spec = content.format_spec
    if isinstance(spec, SingleImageSpecV1):
        if len(spec.headline.strip()) > 120:
            issues.append(
                _issue(
                    "visual.single_image_headline_dense",
                    EditorialIssueSeverity.WARNING,
                    "Single-image headline is too long for a strong first visual read.",
                    "format_spec.headline",
                )
            )
        if len(spec.supporting_copy) > 6:
            issues.append(
                _issue(
                    "visual.single_image_overloaded",
                    EditorialIssueSeverity.WARNING,
                    "Single image carries too many support blocks; consider a carousel or stronger compression.",
                    "format_spec.supporting_copy",
                )
            )

    elif isinstance(spec, CarouselSpecV1):
        if len(spec.slides) < 3:
            issues.append(
                _issue(
                    "visual.carousel_too_short",
                    EditorialIssueSeverity.WARNING,
                    "Carousel has fewer than three semantic beats and may not justify the format.",
                    "format_spec.slides",
                )
            )
        headlines = [normalize_text(slide.headline) for slide in spec.slides]
        if len(headlines) != len(set(headlines)):
            issues.append(
                _issue(
                    "visual.carousel_duplicate_headlines",
                    EditorialIssueSeverity.BLOCKING,
                    "Carousel repeats a slide headline; each page must advance the narrative.",
                    "format_spec.slides",
                )
            )
        if len({slide.role for slide in spec.slides}) < min(3, len(spec.slides)):
            issues.append(
                _issue(
                    "visual.carousel_low_semantic_contrast",
                    EditorialIssueSeverity.WARNING,
                    "Carousel pages use too little role variation; strengthen narrative progression.",
                    "format_spec.slides",
                )
            )

    elif isinstance(spec, InfographicSpecV1):
        if len(spec.sections) < 2:
            issues.append(
                _issue(
                    "visual.infographic_too_thin",
                    EditorialIssueSeverity.WARNING,
                    "Infographic has fewer than two information sections and may not justify the format.",
                    "format_spec.sections",
                )
            )
        labels = [normalize_text(section.label) for section in spec.sections]
        if len(labels) != len(set(labels)):
            issues.append(
                _issue(
                    "visual.infographic_duplicate_labels",
                    EditorialIssueSeverity.BLOCKING,
                    "Infographic repeats section labels instead of creating distinct information groups.",
                    "format_spec.sections",
                )
            )

    # Profile-aware but vertical-neutral checks.
    if profile.copy_policy.target_language != content.language:
        issues.append(
            _issue(
                "profile.language_mismatch",
                EditorialIssueSeverity.BLOCKING,
                "Content language differs from the frozen Profile copy policy.",
                content.content_spec_id,
            )
        )

    if profile.audience and not normalized_visible:
        issues.append(
            _issue(
                "profile.empty_audience_output",
                EditorialIssueSeverity.BLOCKING,
                "Content produced no audience-facing copy.",
                content.content_spec_id,
            )
        )

    # Deduplicate identical codes while preserving deterministic order.
    deduped: list[EditorialIssueV1] = []
    seen: set[str] = set()
    for item in issues:
        if item.code in seen:
            continue
        seen.add(item.code)
        deduped.append(item)
    return tuple(deduped)


def blocking_publishability_issues(
    *,
    content: ContentSpecV1,
    plan: ContentPlanV1,
    profile: ProfileVersion,
) -> tuple[EditorialIssueV1, ...]:
    return tuple(
        issue
        for issue in evaluate_publishability(content=content, plan=plan, profile=profile)
        if issue.severity == EditorialIssueSeverity.BLOCKING
    )
