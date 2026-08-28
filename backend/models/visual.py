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
