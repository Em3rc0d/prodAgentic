from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_TOKEN_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,79}$"
_STORAGE_KEY_PATTERN = r"^renders/[a-z0-9/_\-.]{1,480}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RenderContentType(str, Enum):
    PNG = "image/png"


class RendererThemeV1(FrozenModel):
    background: str = Field(pattern=_TOKEN_PATTERN)
    surface: str = Field(pattern=_TOKEN_PATTERN)
    text: str = Field(pattern=_TOKEN_PATTERN)
    muted_text: str = Field(pattern=_TOKEN_PATTERN)
    accent: str = Field(pattern=_TOKEN_PATTERN)
    border: str = Field(pattern=_TOKEN_PATTERN)
    density: Literal["sparse", "balanced", "dense"]
    spacing_scale: Literal["compact", "standard", "roomy"]
    radius_scale: Literal["sharp", "standard", "soft"]
    icon_language: Literal["outline", "geometric", "expressive"]


class RenderSafeZoneV1(FrozenModel):
    top: int = Field(ge=0, le=512)
    right: int = Field(ge=0, le=512)
    bottom: int = Field(ge=0, le=512)
    left: int = Field(ge=0, le=512)


class ResolvedRenderBlockV1(FrozenModel):
    block_id: str = Field(min_length=1, max_length=128)
    kind: Literal["text", "shape", "icon", "diagram", "divider", "metric"]
    role: Literal["headline", "body", "label", "footer", "microcopy"] | None = None
    text: str | None = Field(default=None, max_length=4_000)
    label: str | None = Field(default=None, max_length=1_000)
    items: tuple[str, ...] = Field(default=(), max_length=32)
    token_ref: str | None = Field(default=None, pattern=_TOKEN_PATTERN)
    icon_ref: str | None = Field(default=None, pattern=_TOKEN_PATTERN)
    shape: Literal["rect", "circle", "line"] | None = None
    editorial_critical: bool = False

    @model_validator(mode="after")
    def validate_kind_payload(self):
        if self.kind == "text":
            if self.text is None or self.role is None:
                raise ValueError("resolved text block requires text and role")
        elif self.kind == "metric":
            if self.text is None:
                raise ValueError("resolved metric block requires text")
        elif self.kind == "diagram":
            if not self.items:
                raise ValueError("resolved diagram block requires at least one label")
        elif self.kind in {"shape", "divider"}:
            if self.token_ref is None:
                raise ValueError(f"resolved {self.kind} block requires token_ref")
            if self.kind == "shape" and self.shape is None:
                raise ValueError("resolved shape block requires shape")
        elif self.kind == "icon" and self.icon_ref is None:
            raise ValueError("resolved icon block requires icon_ref")
        return self


class ResolvedRenderPageV1(FrozenModel):
    page_id: str = Field(min_length=1, max_length=128)
    page_index: int = Field(ge=0, le=19)
    role: Literal["hook", "explain", "evidence", "example", "takeaway", "cta"]
    layout_family: Literal[
        "hero_stack",
        "split_focus",
        "split_evidence",
        "card_grid",
        "evidence_grid",
        "metric_stack",
        "editorial_poster",
    ]
    blocks: tuple[ResolvedRenderBlockV1, ...] = Field(min_length=1, max_length=64)
    alt_text: str | None = Field(default=None, max_length=4_000)


class RendererRequestV1(FrozenModel):
    schema_version: Literal[1] = 1
    contract_version: Literal["RendererRequestV1@1"] = "RendererRequestV1@1"
    render_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    visual_spec_id: str = Field(min_length=1, max_length=128)
    visual_spec_digest: str = Field(pattern=_SHA256_PATTERN)
    content_spec_digest: str = Field(pattern=_SHA256_PATTERN)
    design_profile_digest: str = Field(pattern=_SHA256_PATTERN)
    visual_pattern: str = Field(pattern=_TOKEN_PATTERN)
    format: Literal["single_image", "carousel", "infographic"]
    canvas_width: int = Field(ge=320, le=4096)
    canvas_height: int = Field(ge=320, le=4096)
    safe_zone: RenderSafeZoneV1
    theme: RendererThemeV1
    pages: tuple[ResolvedRenderPageV1, ...] = Field(min_length=1, max_length=20)
    render_input_digest: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def contiguous_pages(self):
        indices = [page.page_index for page in self.pages]
        if indices != list(range(len(self.pages))):
            raise ValueError("renderer page indices must be contiguous and ordered from zero")
        if len({page.page_id for page in self.pages}) != len(self.pages):
            raise ValueError("renderer page IDs must be unique")
        return self


class AssetV1(FrozenModel):
    schema_version: Literal[1] = 1
    asset_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    render_id: str = Field(min_length=1, max_length=128)
    visual_spec_id: str = Field(min_length=1, max_length=128)
    page_id: str = Field(min_length=1, max_length=128)
    page_index: int = Field(ge=0, le=19)
    content_type: RenderContentType = RenderContentType.PNG
    width: int = Field(ge=320, le=4096)
    height: int = Field(ge=320, le=4096)
    byte_size: int = Field(gt=0, le=16 * 1024 * 1024)
    storage_key: str = Field(pattern=_STORAGE_KEY_PATTERN, max_length=512)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    render_input_digest: str = Field(pattern=_SHA256_PATTERN)
    created_at: datetime

    @model_validator(mode="after")
    def storage_key_is_relative_and_normalized(self):
        parts = self.storage_key.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("asset storage_key must be normalized and traversal-free")
        return self


class RenderResultV1(FrozenModel):
    schema_version: Literal[1] = 1
    render_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    visual_spec_id: str = Field(min_length=1, max_length=128)
    visual_spec_digest: str = Field(pattern=_SHA256_PATTERN)
    content_spec_digest: str = Field(pattern=_SHA256_PATTERN)
    design_profile_digest: str = Field(pattern=_SHA256_PATTERN)
    render_input_digest: str = Field(pattern=_SHA256_PATTERN)
    renderer_name: Literal["ChromiumRendererAdapter"] = "ChromiumRendererAdapter"
    renderer_version: str = Field(min_length=1, max_length=120)
    assets: tuple[AssetV1, ...] = Field(min_length=1, max_length=20)
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def result_invariants(self):
        if self.completed_at < self.started_at:
            raise ValueError("render completion cannot precede start")
        if len({asset.asset_id for asset in self.assets}) != len(self.assets):
            raise ValueError("render asset IDs must be unique")
        if len({asset.storage_key for asset in self.assets}) != len(self.assets):
            raise ValueError("render storage keys must be unique")
        indices = [asset.page_index for asset in self.assets]
        if indices != list(range(len(self.assets))):
            raise ValueError("render assets must be contiguous and ordered by page_index")
        for asset in self.assets:
            if asset.tenant_id != self.tenant_id:
                raise ValueError("render asset tenant mismatch")
            if asset.revision_id != self.revision_id:
                raise ValueError("render asset revision mismatch")
            if asset.render_id != self.render_id:
                raise ValueError("render asset render_id mismatch")
            if asset.visual_spec_id != self.visual_spec_id:
                raise ValueError("render asset VisualSpec mismatch")
            if asset.render_input_digest != self.render_input_digest:
                raise ValueError("render asset input digest mismatch")
        return self


def canonical_render_sha256(payload: BaseModel | dict, *, exclude: set[str] | None = None) -> str:
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
