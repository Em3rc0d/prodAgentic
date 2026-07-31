from pydantic import BaseModel
from enum import Enum
from typing import Optional

class AspectRatio(str, Enum):
    WIDESCREEN = "16:9"
    SQUARE = "1:1"
    PORTRAIT = "9:16"
    PANORAMIC = "2:1"

class VisualStyle(str, Enum):
    REALISTIC = "realistic"
    ILLUSTRATION = "illustration"
    CYBERPUNK = "cyberpunk"
    WATERCOLOR = "watercolor"
    DEFAULT = ""

class RenderStatus(str, Enum):
    QUEUED = "QUEUED"
    RENDERING = "RENDERING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class VisualRenderRequest(BaseModel):
    run_id: str
    idempotency_key: str
    prompt: str
    aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    style: VisualStyle = VisualStyle.DEFAULT

class VisualRenderResponse(BaseModel):
    render_id: str
    status: RenderStatus
    provider: str
    asset_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    prompt_used: str
    error_message: Optional[str] = None
