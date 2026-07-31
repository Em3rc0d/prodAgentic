from abc import ABC, abstractmethod
import urllib.parse
from typing import Optional
from pydantic import BaseModel

class ImageRenderResult(BaseModel):
    url: str
    prompt_used: str
    aspect_ratio: str
    width: int
    height: int
    remaining_credits: Optional[int] = None

class ImageRenderProvider(ABC):
    @abstractmethod
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        pass

# Exact aspect ratio → (width, height) mapping — matches the approved contract
ASPECT_RATIO_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1":  (1024, 1024),
    "4:5":  (820,  1024),
    "16:9": (1280, 720),
}

# Exact style list — matches the approved contract
APPROVED_STYLES = {
    "technical_editorial",
    "cinematic",
    "minimal",
    "illustration",
    "photorealistic",
    "",  # empty = no style modifier
}

class PollinationsImageAdapter(ImageRenderProvider):
    """
    Server-side adapter for Pollinations AI.
    Dimensions are derived from the approved aspect-ratio contract.
    """
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        if aspect_ratio not in ASPECT_RATIO_DIMENSIONS:
            raise ValueError(
                f"Unsupported aspect_ratio '{aspect_ratio}'. "
                f"Allowed: {sorted(ASPECT_RATIO_DIMENSIONS)}"
            )
        if style not in APPROVED_STYLES:
            raise ValueError(
                f"Unsupported style '{style}'. "
                f"Allowed: {sorted(s for s in APPROVED_STYLES if s)}"
            )

        width, height = ASPECT_RATIO_DIMENSIONS[aspect_ratio]
        enhanced_prompt = f"{prompt} {style}".strip() if style else prompt
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&nologo=true"
        )

        return ImageRenderResult(
            url=url,
            prompt_used=enhanced_prompt,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        )
