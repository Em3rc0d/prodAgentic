from __future__ import annotations

from application.visual.validation import copy_reference_map
from domain.production.models import ContentSpecV1, canonical_sha256 as production_sha256
from domain.rendering.models import (
    RenderSafeZoneV1,
    RendererRequestV1,
    RendererThemeV1,
    ResolvedRenderBlockV1,
    ResolvedRenderPageV1,
    canonical_render_sha256,
)
from domain.visual.models import (
    DesignProfileV1,
    DiagramBlockV1,
    DividerBlockV1,
    IconBlockV1,
    ImageBlockV1,
    MetricBlockV1,
    RenderStrategy,
    ShapeBlockV1,
    TextBlockV1,
    VisualSpecV1,
    canonical_visual_sha256,
)


class UnsupportedRenderInput(ValueError):
    pass


_EXTERNAL_ASSET_STRATEGIES = {
    RenderStrategy.GENERATED_BACKGROUND,
    RenderStrategy.GENERATED_VISUAL_PLUS_COMPOSITE,
    RenderStrategy.PHOTO_OVERLAY,
}


def _resolve_ref(copy_map: dict[str, str], ref: str) -> str:
    try:
        return copy_map[ref]
    except KeyError as exc:
        raise UnsupportedRenderInput(f"renderer received unknown copy_ref: {ref}") from exc


def _resolve_block(block, *, copy_map: dict[str, str]) -> ResolvedRenderBlockV1:
    if isinstance(block, TextBlockV1):
        if block.copy_ref is not None:
            text = _resolve_ref(copy_map, block.copy_ref)
        elif block.literal is not None and not block.editorial_critical:
            text = block.literal
        else:
            raise UnsupportedRenderInput("renderer cannot resolve text authority")
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="text",
            role=block.role,
            text=text,
            editorial_critical=block.editorial_critical,
        )
    if isinstance(block, ShapeBlockV1):
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="shape",
            shape=block.shape.value,
            token_ref=block.token_ref,
        )
    if isinstance(block, IconBlockV1):
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="icon",
            icon_ref=block.icon_ref,
        )
    if isinstance(block, DividerBlockV1):
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="divider",
            token_ref=block.token_ref,
        )
    if isinstance(block, MetricBlockV1):
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="metric",
            text=_resolve_ref(copy_map, block.copy_ref),
            label=_resolve_ref(copy_map, block.label_ref) if block.label_ref else None,
            editorial_critical=True,
        )
    if isinstance(block, DiagramBlockV1):
        return ResolvedRenderBlockV1(
            block_id=block.block_id,
            kind="diagram",
            items=tuple(_resolve_ref(copy_map, ref) for ref in block.label_refs),
            editorial_critical=True,
        )
    if isinstance(block, ImageBlockV1):
        raise UnsupportedRenderInput("S5 deterministic renderer does not yet own external image requirements")
    raise UnsupportedRenderInput(f"unsupported VisualBlock type: {type(block).__name__}")


def build_renderer_request(
    *,
    revision_id: str,
    visual_spec: VisualSpecV1,
    content: ContentSpecV1,
    design_profile: DesignProfileV1,
    renderer_name: str,
    renderer_version: str,
) -> RendererRequestV1:
    if visual_spec.revision_id != revision_id:
        raise UnsupportedRenderInput("VisualSpec revision authority mismatch")
    if visual_spec.content_spec_id != content.content_spec_id:
        raise UnsupportedRenderInput("VisualSpec ContentSpec authority mismatch")
    if visual_spec.style.design_profile_ref != design_profile.design_profile_id:
        raise UnsupportedRenderInput("VisualSpec DesignProfile authority mismatch")
    if visual_spec.style.design_profile_digest != design_profile.digest:
        raise UnsupportedRenderInput("VisualSpec DesignProfile digest mismatch")
    if visual_spec.asset_requirements:
        raise UnsupportedRenderInput("S5 deterministic renderer requires zero unresolved asset requirements")
    if visual_spec.render_strategy in _EXTERNAL_ASSET_STRATEGIES:
        raise UnsupportedRenderInput("external/generated image render strategy is not certified in S5 deterministic V1")

    copy_map = copy_reference_map(content)
    pages = tuple(
        ResolvedRenderPageV1(
            page_id=page.page_id,
            page_index=page.page_index,
            role=page.role.value,
            layout_family=page.layout_family.value,
            blocks=tuple(_resolve_block(block, copy_map=copy_map) for block in page.blocks),
            alt_text=visual_spec.alt_text_plan or content.alt_text_draft,
        )
        for page in visual_spec.pages
    )
    theme = RendererThemeV1(
        background=design_profile.palette.background,
        surface=design_profile.palette.surface,
        text=design_profile.palette.text,
        muted_text=design_profile.palette.muted_text,
        accent=design_profile.palette.accent,
        border=design_profile.palette.border,
        density=design_profile.density.value,
        spacing_scale=design_profile.spacing_scale.value,
        radius_scale=design_profile.radius_scale.value,
        icon_language=design_profile.icon_language.value,
    )
    safe_zone = RenderSafeZoneV1(**visual_spec.canvas.safe_zone.model_dump())
    visual_spec_digest = canonical_visual_sha256(visual_spec)
    content_spec_digest = production_sha256(content)

    semantic_payload = {
        "contract_version": "RendererRequestV1@1",
        "renderer_name": renderer_name,
        "renderer_version": renderer_version,
        "revision_id": revision_id,
        "visual_spec_id": visual_spec.visual_spec_id,
        "visual_spec_digest": visual_spec_digest,
        "content_spec_digest": content_spec_digest,
        "design_profile_digest": design_profile.digest,
        "visual_pattern": visual_spec.visual_pattern,
        "format": visual_spec.format.value,
        "canvas_width": visual_spec.canvas.width,
        "canvas_height": visual_spec.canvas.height,
        "safe_zone": safe_zone.model_dump(mode="json"),
        "theme": theme.model_dump(mode="json"),
        "pages": [page.model_dump(mode="json") for page in pages],
    }
    render_input_digest = canonical_render_sha256(semantic_payload)
    return RendererRequestV1(
        render_id=f"render-{render_input_digest}",
        revision_id=revision_id,
        visual_spec_id=visual_spec.visual_spec_id,
        visual_spec_digest=visual_spec_digest,
        content_spec_digest=content_spec_digest,
        design_profile_digest=design_profile.digest,
        visual_pattern=visual_spec.visual_pattern,
        format=visual_spec.format.value,
        canvas_width=visual_spec.canvas.width,
        canvas_height=visual_spec.canvas.height,
        safe_zone=safe_zone,
        theme=theme,
        pages=pages,
        render_input_digest=render_input_digest,
    )
