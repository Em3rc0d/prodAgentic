from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_TOKEN_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,79}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VisualFormat(str, Enum):
    SINGLE_IMAGE = "single_image"
    CAROUSEL = "carousel"
    INFOGRAPHIC = "infographic"


class RenderStrategy(str, Enum):
    COMPOSED_STATIC = "COMPOSED_STATIC"
    GENERATED_BACKGROUND = "GENERATED_BACKGROUND"
    GENERATED_VISUAL_PLUS_COMPOSITE = "GENERATED_VISUAL_PLUS_COMPOSITE"
    DIAGRAM = "DIAGRAM"
    CAROUSEL = "CAROUSEL"
    INFOGRAPHIC = "INFOGRAPHIC"
    PHOTO_OVERLAY = "PHOTO_OVERLAY"


class Density(str, Enum):
    SPARSE = "sparse"
    BALANCED = "balanced"
    DENSE = "dense"


class VisualPageRole(str, Enum):
    HOOK = "hook"
    EXPLAIN = "explain"
    EVIDENCE = "evidence"
    EXAMPLE = "example"
    TAKEAWAY = "takeaway"
    CTA = "cta"


class LayoutFamily(str, Enum):
    HERO_STACK = "hero_stack"
    SPLIT_FOCUS = "split_focus"
    SPLIT_EVIDENCE = "split_evidence"
    CARD_GRID = "card_grid"
    EVIDENCE_GRID = "evidence_grid"
    METRIC_STACK = "metric_stack"
    EDITORIAL_POSTER = "editorial_poster"


class IconLanguage(str, Enum):
    OUTLINE = "outline"
    GEOMETRIC = "geometric"
    EXPRESSIVE = "expressive"


class ImageTreatment(str, Enum):
    EDITORIAL_CROP = "editorial_crop"
    MONOCHROME = "monochrome"
    HIGH_CONTRAST = "high_contrast"
    NONE = "none"


class SpacingScale(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    ROOMY = "roomy"


class RadiusScale(str, Enum):
    SHARP = "sharp"
    STANDARD = "standard"
    SOFT = "soft"


class SafeZonePolicy(str, Enum):
    FEED_PORTRAIT_V1 = "feed_portrait_v1"


class AssetRequirementKind(str, Enum):
    OWNED_IMAGE = "owned_image"
    GENERATED_IMAGE = "generated_image"
    ICON_SET = "icon_set"
    PHOTO = "photo"


class ShapeKind(str, Enum):
    RECT = "rect"
    CIRCLE = "circle"
    LINE = "line"


class TypographyRolesV1(FrozenModel):
    display: str = Field(pattern=_TOKEN_PATTERN)
    heading: str = Field(pattern=_TOKEN_PATTERN)
    body: str = Field(pattern=_TOKEN_PATTERN)
    mono: str = Field(pattern=_TOKEN_PATTERN)


class PaletteMappingV1(FrozenModel):
    background: str = Field(pattern=_TOKEN_PATTERN)
    surface: str = Field(pattern=_TOKEN_PATTERN)
    text: str = Field(pattern=_TOKEN_PATTERN)
    muted_text: str = Field(pattern=_TOKEN_PATTERN)
    accent: str = Field(pattern=_TOKEN_PATTERN)
    border: str = Field(pattern=_TOKEN_PATTERN)


class SafeZoneProfileV1(FrozenModel):
    policy: SafeZonePolicy = SafeZonePolicy.FEED_PORTRAIT_V1
    inset_px: int = Field(ge=32, le=160)


class DesignProfileV1(FrozenModel):
    schema_version: Literal[1] = 1
    mapping_version: Literal["mk1-design-profile-v1"] = "mk1-design-profile-v1"
    design_profile_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=1)
    source_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    typography: TypographyRolesV1
    palette: PaletteMappingV1
    density: Density
    spacing_scale: SpacingScale
    radius_scale: RadiusScale
    icon_language: IconLanguage
    image_treatment: ImageTreatment
    layout_family_preferences: tuple[LayoutFamily, ...] = Field(min_length=1, max_length=7)
    safe_zone: SafeZoneProfileV1
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafeZoneV1(FrozenModel):
    top: int = Field(ge=0, le=512)
    right: int = Field(ge=0, le=512)
    bottom: int = Field(ge=0, le=512)
    left: int = Field(ge=0, le=512)


class CanvasV1(FrozenModel):
    width: int = Field(ge=320, le=4096)
    height: int = Field(ge=320, le=4096)
    unit: Literal["px"] = "px"
    safe_zone: SafeZoneV1

    @model_validator(mode="after")
    def safe_zone_fits_canvas(self):
        if self.safe_zone.left + self.safe_zone.right >= self.width:
            raise ValueError("horizontal safe zone must leave drawable width")
        if self.safe_zone.top + self.safe_zone.bottom >= self.height:
            raise ValueError("vertical safe zone must leave drawable height")
        return self


class VisualStyleV1(FrozenModel):
    design_profile_ref: str = Field(min_length=1, max_length=128)
    design_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    density: Density
    image_treatment: ImageTreatment
    icon_language: IconLanguage


class TextBlockV1(FrozenModel):
    kind: Literal["text"] = "text"
    block_id: str = Field(min_length=1, max_length=128)
    copy_ref: str | None = Field(default=None, min_length=1, max_length=512)
    literal: str | None = Field(default=None, min_length=1, max_length=240)
    editorial_critical: bool = True
    role: Literal["headline", "body", "label", "footer", "microcopy"] = "body"

    @model_validator(mode="after")
    def copy_authority(self):
        if self.editorial_critical:
            if not self.copy_ref or self.literal is not None:
                raise ValueError("critical text must use copy_ref and cannot use literal")
        else:
            if (self.copy_ref is None) == (self.literal is None):
                raise ValueError("non-critical text requires exactly one of copy_ref or literal")
        return self


class ShapeBlockV1(FrozenModel):
    kind: Literal["shape"] = "shape"
    block_id: str = Field(min_length=1, max_length=128)
    shape: ShapeKind
    token_ref: str = Field(pattern=_TOKEN_PATTERN)


class IconBlockV1(FrozenModel):
    kind: Literal["icon"] = "icon"
    block_id: str = Field(min_length=1, max_length=128)
    icon_ref: str = Field(pattern=_TOKEN_PATTERN)
    decorative: bool = True


class ImageBlockV1(FrozenModel):
    kind: Literal["image"] = "image"
    block_id: str = Field(min_length=1, max_length=128)
    asset_requirement_ref: str = Field(min_length=1, max_length=128)
    treatment: ImageTreatment


class DiagramBlockV1(FrozenModel):
    kind: Literal["diagram"] = "diagram"
    block_id: str = Field(min_length=1, max_length=128)
    diagram_kind: Literal["flow", "relationship", "comparison"]
    label_refs: tuple[str, ...] = Field(default=(), max_length=32)


class DividerBlockV1(FrozenModel):
    kind: Literal["divider"] = "divider"
    block_id: str = Field(min_length=1, max_length=128)
    token_ref: str = Field(pattern=_TOKEN_PATTERN)


class MetricBlockV1(FrozenModel):
    kind: Literal["metric"] = "metric"
    block_id: str = Field(min_length=1, max_length=128)
    copy_ref: str = Field(min_length=1, max_length=512)
    label_ref: str | None = Field(default=None, min_length=1, max_length=512)


VisualBlockV1 = (
    TextBlockV1
    | ShapeBlockV1
    | IconBlockV1
    | ImageBlockV1
    | DiagramBlockV1
    | DividerBlockV1
    | MetricBlockV1
)


class VisualPageV1(FrozenModel):
    page_id: str = Field(min_length=1, max_length=128)
    page_index: int = Field(ge=0, le=19)
    role: VisualPageRole
    layout_family: LayoutFamily
    blocks: tuple[VisualBlockV1, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_block_ids(self):
        ids = [block.block_id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("block IDs must be unique within a page")
        return self


class AssetRequirementV1(FrozenModel):
    requirement_id: str = Field(min_length=1, max_length=128)
    kind: AssetRequirementKind
    purpose: str = Field(min_length=1, max_length=240)
    owned_bytes_required: Literal[True] = True
    accepted_content_types: tuple[
        Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"], ...
    ] = Field(min_length=1, max_length=4)


class VisualSpecV1(FrozenModel):
    schema_version: Literal[1] = 1
    visual_spec_id: str = Field(min_length=1, max_length=128)
    spec_version: Literal[1] = 1
    content_spec_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    format: VisualFormat
    canvas: CanvasV1
    render_strategy: RenderStrategy
    visual_pattern: str = Field(pattern=_TOKEN_PATTERN)
    style: VisualStyleV1
    pages: tuple[VisualPageV1, ...] = Field(min_length=1, max_length=20)
    asset_requirements: tuple[AssetRequirementV1, ...] = Field(default=(), max_length=16)
    alt_text_plan: str | None = Field(default=None, max_length=4_000)
    supersedes_visual_spec_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def structural_invariants(self):
        page_ids = [page.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page IDs must be unique")
        indices = [page.page_index for page in self.pages]
        if indices != list(range(len(self.pages))):
            raise ValueError("page indices must be contiguous and ordered from zero")

        requirement_ids = [item.requirement_id for item in self.asset_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("asset requirement IDs must be unique")

        image_requirement_refs = {
            block.asset_requirement_ref
            for page in self.pages
            for block in page.blocks
            if isinstance(block, ImageBlockV1)
        }
        unknown = image_requirement_refs - set(requirement_ids)
        if unknown:
            raise ValueError(f"image blocks reference unknown asset requirements: {sorted(unknown)}")

        if self.format == VisualFormat.SINGLE_IMAGE:
            if len(self.pages) != 1:
                raise ValueError("single_image VisualSpec requires exactly one page")
            if self.render_strategy in {RenderStrategy.CAROUSEL, RenderStrategy.INFOGRAPHIC}:
                raise ValueError("single_image render strategy is incompatible")
        elif self.format == VisualFormat.CAROUSEL:
            if len(self.pages) < 2:
                raise ValueError("carousel VisualSpec requires at least two pages")
            if self.render_strategy != RenderStrategy.CAROUSEL:
                raise ValueError("carousel VisualSpec requires CAROUSEL render strategy")
        elif self.format == VisualFormat.INFOGRAPHIC:
            if len(self.pages) != 1:
                raise ValueError("infographic V1 requires exactly one page")
            if self.render_strategy != RenderStrategy.INFOGRAPHIC:
                raise ValueError("infographic VisualSpec requires INFOGRAPHIC render strategy")
        return self


def canonical_visual_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
    if isinstance(payload, BaseModel):
        value = payload.model_dump(mode="json", exclude=exclude or set())
    else:
        value = payload
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")
