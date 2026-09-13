from __future__ import annotations

from domain.production.models import (
    CarouselSpecV1,
    ContentSpecV1,
    InfographicSpecV1,
    SingleImageSpecV1,
)
from domain.visual.models import (
    CanvasV1,
    DesignProfileV1,
    DiagramBlockV1,
    DividerBlockV1,
    IconBlockV1,
    LayoutFamily,
    RenderStrategy,
    SafeZoneV1,
    ShapeBlockV1,
    ShapeKind,
    TextBlockV1,
    VisualFormat,
    VisualPageRole,
    VisualPageV1,
    VisualSpecV1,
    VisualStyleV1,
)


class UnsupportedVisualFormat(ValueError):
    pass


_ROLE_LAYOUT_CANDIDATES: dict[VisualPageRole, tuple[LayoutFamily, ...]] = {
    VisualPageRole.HOOK: (LayoutFamily.EDITORIAL_POSTER, LayoutFamily.HERO_STACK),
    VisualPageRole.EXPLAIN: (LayoutFamily.SPLIT_EVIDENCE, LayoutFamily.CARD_GRID),
    VisualPageRole.EVIDENCE: (LayoutFamily.EVIDENCE_GRID, LayoutFamily.SPLIT_EVIDENCE),
    VisualPageRole.EXAMPLE: (LayoutFamily.CARD_GRID, LayoutFamily.SPLIT_FOCUS),
    VisualPageRole.TAKEAWAY: (LayoutFamily.SPLIT_FOCUS, LayoutFamily.HERO_STACK),
    VisualPageRole.CTA: (LayoutFamily.HERO_STACK, LayoutFamily.SPLIT_FOCUS),
}


def _layout_for(role: VisualPageRole, profile: DesignProfileV1) -> LayoutFamily:
    for candidate in _ROLE_LAYOUT_CANDIDATES[role]:
        if candidate in profile.layout_family_preferences:
            return candidate
    return profile.layout_family_preferences[0]


def _canvas(profile: DesignProfileV1) -> CanvasV1:
    inset = profile.safe_zone.inset_px
    return CanvasV1(
        width=1080,
        height=1350,
        safe_zone=SafeZoneV1(top=inset, right=inset, bottom=inset, left=inset),
    )


def _style(profile: DesignProfileV1) -> VisualStyleV1:
    return VisualStyleV1(
        design_profile_ref=profile.design_profile_id,
        design_profile_digest=profile.digest,
        density=profile.density,
        image_treatment=profile.image_treatment,
        icon_language=profile.icon_language,
    )


def _surface(block_id: str, profile: DesignProfileV1) -> ShapeBlockV1:
    return ShapeBlockV1(
        block_id=block_id,
        shape=ShapeKind.RECT,
        token_ref=profile.palette.surface,
    )


def _divider(block_id: str, profile: DesignProfileV1) -> DividerBlockV1:
    return DividerBlockV1(block_id=block_id, token_ref=profile.palette.border)


def _accent_icon(block_id: str) -> IconBlockV1:
    # Renderer owns the concrete glyph. VisualSpec only communicates a bounded
    # semantic accent, keeping generated/external assets outside this slice.
    return IconBlockV1(block_id=block_id, icon_ref="icon.editorial_signal", decorative=True)


def _text(*, block_id: str, copy_ref: str, role: str = "body") -> TextBlockV1:
    return TextBlockV1(
        block_id=block_id,
        copy_ref=copy_ref,
        editorial_critical=True,
        role=role,
    )


def _single_image_pattern(content: SingleImageSpecV1, profile: DesignProfileV1) -> str:
    if len(content.supporting_copy) >= 2:
        return "single_image.action_framework.v2"
    if LayoutFamily.EDITORIAL_POSTER in profile.layout_family_preferences:
        return "single_image.editorial_poster.v2"
    return "single_image.focus_card.v2"


def _carousel_pattern(content: CarouselSpecV1) -> str:
    roles = {slide.role for slide in content.slides}
    if "evidence" in roles or "example" in roles:
        return "carousel.evidence_progression.v2"
    if "cta" in roles and "takeaway" in roles:
        return "carousel.narrative_progression.v2"
    return "carousel.semantic_pages.v2"


def _infographic_pattern(content: InfographicSpecV1) -> str:
    if any(section.relationship for section in content.sections):
        return "infographic.relationship_map.v2"
    return "infographic.section_grid.v2"


def build_visual_spec(
    *,
    visual_spec_id: str,
    revision_id: str,
    content: ContentSpecV1,
    design_profile: DesignProfileV1,
    supersedes_visual_spec_id: str | None = None,
) -> VisualSpecV1:
    if content.format == "text":
        raise UnsupportedVisualFormat("text-only ContentSpec does not require VisualSpec")

    format_spec = content.format_spec
    pages: list[VisualPageV1] = []

    if isinstance(format_spec, SingleImageSpecV1):
        blocks = [
            _surface("surface", design_profile),
            _accent_icon("signal"),
            _text(
                block_id="headline",
                copy_ref="content_spec.format_spec.headline",
                role="headline",
            ),
            _divider("headline-divider", design_profile),
        ]
        support_refs = tuple(
            f"content_spec.format_spec.supporting_copy[{index}]"
            for index in range(len(format_spec.supporting_copy))
        )
        if len(support_refs) >= 2:
            blocks.append(
                DiagramBlockV1(
                    block_id="support-framework",
                    diagram_kind="flow",
                    label_refs=support_refs,
                )
            )
        else:
            blocks.extend(
                _text(
                    block_id=f"support-{index}",
                    copy_ref=ref,
                    role="body",
                )
                for index, ref in enumerate(support_refs)
            )
        if format_spec.footer is not None:
            blocks.append(
                _text(
                    block_id="footer",
                    copy_ref="content_spec.format_spec.footer",
                    role="footer",
                )
            )
        pages.append(
            VisualPageV1(
                page_id="single-image-main",
                page_index=0,
                role=VisualPageRole.HOOK,
                layout_family=_layout_for(VisualPageRole.HOOK, design_profile),
                blocks=tuple(blocks),
            )
        )
        visual_format = VisualFormat.SINGLE_IMAGE
        strategy = RenderStrategy.COMPOSED_STATIC
        pattern = _single_image_pattern(format_spec, design_profile)

    elif isinstance(format_spec, CarouselSpecV1):
        for index, slide in enumerate(format_spec.slides):
            role = VisualPageRole(slide.role)
            prefix = f"content_spec.format_spec.slides[{slide.slide_id}]"
            blocks = [_surface(f"surface-{slide.slide_id}", design_profile)]
            if role in {VisualPageRole.HOOK, VisualPageRole.TAKEAWAY, VisualPageRole.CTA}:
                blocks.append(_accent_icon(f"signal-{slide.slide_id}"))
            blocks.append(
                _text(
                    block_id=f"headline-{slide.slide_id}",
                    copy_ref=f"{prefix}.headline",
                    role="headline",
                )
            )
            if role in {VisualPageRole.HOOK, VisualPageRole.TAKEAWAY, VisualPageRole.CTA}:
                blocks.append(_divider(f"divider-{slide.slide_id}", design_profile))
            if slide.body is not None:
                blocks.append(
                    _text(
                        block_id=f"body-{slide.slide_id}",
                        copy_ref=f"{prefix}.body",
                        role="body",
                    )
                )
            bullet_refs = tuple(
                f"{prefix}.bullets[{bullet_index}]"
                for bullet_index in range(len(slide.bullets))
            )
            if len(bullet_refs) >= 2:
                blocks.append(
                    DiagramBlockV1(
                        block_id=f"framework-{slide.slide_id}",
                        diagram_kind="flow" if role in {VisualPageRole.EXPLAIN, VisualPageRole.EXAMPLE} else "relationship",
                        label_refs=bullet_refs,
                    )
                )
            else:
                blocks.extend(
                    _text(
                        block_id=f"bullet-{slide.slide_id}-{bullet_index}",
                        copy_ref=ref,
                        role="body",
                    )
                    for bullet_index, ref in enumerate(bullet_refs)
                )
            pages.append(
                VisualPageV1(
                    page_id=f"page-{slide.slide_id}",
                    page_index=index,
                    role=role,
                    layout_family=_layout_for(role, design_profile),
                    blocks=tuple(blocks),
                )
            )
        visual_format = VisualFormat.CAROUSEL
        strategy = RenderStrategy.CAROUSEL
        pattern = _carousel_pattern(format_spec)

    elif isinstance(format_spec, InfographicSpecV1):
        blocks = [
            _surface("surface", design_profile),
            _accent_icon("signal"),
            _text(
                block_id="title",
                copy_ref="content_spec.format_spec.title",
                role="headline",
            ),
            _divider("title-divider", design_profile),
        ]
        relationship_refs: list[str] = []
        for section_index, section in enumerate(format_spec.sections):
            prefix = f"content_spec.format_spec.sections[{section.section_id}]"
            if section_index > 0:
                blocks.append(_divider(f"section-divider-{section.section_id}", design_profile))
            blocks.append(
                _text(
                    block_id=f"label-{section.section_id}",
                    copy_ref=f"{prefix}.label",
                    role="label",
                )
            )
            blocks.append(
                _text(
                    block_id=f"value-{section.section_id}",
                    copy_ref=f"{prefix}.value_or_copy",
                    role="body",
                )
            )
            if section.relationship is not None:
                relationship_refs.append(f"{prefix}.relationship")
        if relationship_refs:
            blocks.append(
                DiagramBlockV1(
                    block_id="relationships",
                    diagram_kind="relationship",
                    label_refs=tuple(relationship_refs),
                )
            )
        role = VisualPageRole.EXPLAIN
        pages.append(
            VisualPageV1(
                page_id="infographic-main",
                page_index=0,
                role=role,
                layout_family=_layout_for(role, design_profile),
                blocks=tuple(blocks),
            )
        )
        visual_format = VisualFormat.INFOGRAPHIC
        strategy = RenderStrategy.INFOGRAPHIC
        pattern = _infographic_pattern(format_spec)
    else:
        raise UnsupportedVisualFormat(f"unsupported format spec: {type(format_spec).__name__}")

    return VisualSpecV1(
        visual_spec_id=visual_spec_id,
        content_spec_id=content.content_spec_id,
        revision_id=revision_id,
        format=visual_format,
        canvas=_canvas(design_profile),
        render_strategy=strategy,
        visual_pattern=pattern,
        style=_style(design_profile),
        pages=tuple(pages),
        asset_requirements=(),
        alt_text_plan=content.alt_text_draft,
        supersedes_visual_spec_id=supersedes_visual_spec_id,
    )
