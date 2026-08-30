from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class AspectRatio(str, Enum):
    """Approved aspect ratios — must match ASPECT_RATIO_DIMENSIONS in image.py."""
    SQUARE = "1:1"
    PORTRAIT = "4:5"
    WIDESCREEN = "16:9"


class VisualStyle(str, Enum):
    """Approved styles — must match APPROVED_STYLES in image.py."""
    TECHNICAL_EDITORIAL = "technical_editorial"
    CINEMATIC = "cinematic"
    MINIMAL = "minimal"
    ILLUSTRATION = "illustration"
    PHOTOREALISTIC = "photorealistic"
    DEFAULT = ""


class RenderStatus(str, Enum):
    QUEUED = "QUEUED"
    RENDERING = "RENDERING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VisualRenderRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=256)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    prompt: str = Field(..., min_length=1, max_length=2048)
    # LinkedIn feed-first default. Callers may still explicitly request square or widescreen.
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT
    style: VisualStyle = VisualStyle.TECHNICAL_EDITORIAL

    # HYBRID-VISUAL-01: for server-selected deterministic formats the browser
    # rasterizes an exact SVG/layout into PNG. The backend still owns authority:
    # it validates the PNG, byte digest, dimensions and run-bound renderer choice
    # before persisting the asset. These fields are ignored/rejected for
    # generative illustration renders.
    deterministic_png_base64: Optional[str] = Field(default=None, max_length=14_000_000)
    deterministic_png_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class VisualRenderResponse(BaseModel):
    render_id: str
    status: RenderStatus
    provider: str
    asset_url: Optional[str] = None
    asset_sha256: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    prompt_used: str
    error_message: Optional[str] = None
