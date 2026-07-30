from abc import ABC, abstractmethod
import urllib.parse
from typing import Optional
from pydantic import BaseModel

class ImageRenderResult(BaseModel):
    url: str
    prompt_used: str
    aspect_ratio: str
    remaining_credits: Optional[int] = None

class ImageRenderProvider(ABC):
    @abstractmethod
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        pass

class PollinationsImageAdapter(ImageRenderProvider):
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        # Construct the pollinations URL
        # e.g., https://image.pollinations.ai/prompt/{prompt}?width=800&height=400&nologo=true
        
        dimensions = "width=800&height=400" if aspect_ratio == "2:1" or aspect_ratio == "16:9" else "width=800&height=800"
        
        enhanced_prompt = f"{prompt} {style}".strip()
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?{dimensions}&nologo=true"
        
        return ImageRenderResult(
            url=url,
            prompt_used=enhanced_prompt,
            aspect_ratio=aspect_ratio,
            remaining_credits=None # Unlimited for Pollinations
        )
