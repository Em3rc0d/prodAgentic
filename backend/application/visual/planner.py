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
    VisualPageRole.HOOK: (LayoutFamily.HERO_STACK, LayoutFamily.EDITORIAL_POSTER),
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
            ShapeBlockV1(block_id="surface", shape=ShapeKind.RECT, token_ref=design_profile.palette.surface),
            TextBlockV1(
                block_id="headline",
                copy_ref="content_spec.format_spec.headline",
                editorial_critical=True,
                role="headline",
            ),
        ]
        blocks.extend(
            TextBlockV1(
                block_id=f"support-{index}",
                copy_ref=f"content_spec.format_spec.supporting_copy[{index}]",
                editorial_critical=True,
                role="body",
            )
            for index in range(len(format_spec.supporting_copy))
        )
        if format_spec.footer is not None:
            blocks.append(
                TextBlockV1(
                    block_id="footer",
                    copy_ref="content_spec.format_spec.footer",
                    editorial_critical=True,
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
        pattern = "single_image.editorial_poster.v1"

    elif isinstance(format_spec, CarouselSpecV1):
        for index, slide in enumerate(format_spec.slides):
            role = VisualPageRole(slide.role)
            prefix = f"content_spec.format_spec.slides[{slide.slide_id}]"
            blocks = [
                ShapeBlockV1(
                    block_id=f"surface-{slide.slide_id}",
                    shape=ShapeKind.RECT,
                    token_ref=design_profile.palette.surface,
                ),
                TextBlockV1(
                    block_id=f"headline-{slide.slide_id}",
                    copy_ref=f"{prefix}.headline",
                    editorial_critical=True,
                    role="headline",
                ),
            ]
            if slide.body is not None:
                blocks.append(
                    TextBlockV1(
                        block_id=f"body-{slide.slide_id}",
                        copy_ref=f"{prefix}.body",
                        editorial_critical=True,
                        role="body",
                    )
                )
            blocks.extend(
                TextBlockV1(
                    block_id=f"bullet-{slide.slide_id}-{bullet_index}",
                    copy_ref=f"{prefix}.bullets[{bullet_index}]",
                    editorial_critical=True,
                    role="body",
                )
                for bullet_index in range(len(slide.bullets))
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
        pattern = "carousel.semantic_pages.v1"

    elif isinstance(format_spec, InfographicSpecV1):
        blocks = [
            ShapeBlockV1(block_id="surface", shape=ShapeKind.RECT, token_ref=design_profile.palette.surface),
            TextBlockV1(
                block_id="title",
                copy_ref="content_spec.format_spec.title",
                editorial_critical=True,
                role="headline",
            ),
        ]
        for section in format_spec.sections:
            prefix = f"content_spec.format_spec.sections[{section.section_id}]"
            blocks.append(
                TextBlockV1(
                    block_id=f"label-{section.section_id}",
                    copy_ref=f"{prefix}.label",
                    editorial_critical=True,
                    role="label",
                )
            )
            blocks.append(
                TextBlockV1(
                    block_id=f"value-{section.section_id}",
                    copy_ref=f"{prefix}.value_or_copy",
                    editorial_critical=True,
                    role="body",
                )
            )
            if section.relationship is not None:
                blocks.append(
                    TextBlockV1(
                        block_id=f"relationship-{section.section_id}",
                        copy_ref=f"{prefix}.relationship",
                        editorial_critical=True,
                        role="body",
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
        pattern = "infographic.section_grid.v1"
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
