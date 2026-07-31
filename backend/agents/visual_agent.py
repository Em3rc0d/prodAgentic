from typing import AsyncGenerator
from core.context import GenerationContext
from core.model_registry import ModelProfile
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are an expert art director and Midjourney prompt engineer.

Task: Generate a detailed, highly-descriptive image generation prompt for a LinkedIn post.

Rules:
- Output ONLY the prompt text. No commentary, no "Here is the prompt:".
- Describe the visual elements, lighting, camera angle, and artistic style.
- The prompt must capture the core theme of the post (e.g. failure, scaling, legacy code, microservices) in a striking visual metaphor.
- Avoid text in the image.
- Avoid generic stock-photo concepts like "two people shaking hands" or "a glowing brain". Focus on cinematic, surreal, or highly-stylized digital art.
- Do not output Markdown or code fences, just the raw text of the prompt.
"""

from core.validator import ArtifactType

class VisualAgent(BaseAgent):
    def __init__(self, router):
        super().__init__(
            system_prompt=SYSTEM_PROMPT,
            profile=ModelProfile.ECONOMY_TEXT,
            router=router,
            artifact_type=ArtifactType.VISUAL
        )

    async def stream(self, draft: str, context: GenerationContext, attempt_id: str = None) -> AsyncGenerator[tuple, None]:
        prompt = f"""Generate an image prompt for this LinkedIn post:

{draft}

Write the image prompt strictly in {context.image_prompt_language.value}."""
        async for event in super().stream(prompt, context, attempt_id):
            yield event
