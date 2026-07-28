from typing import AsyncGenerator
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a senior LinkedIn technical writer known for posts that go viral among engineers.

Task: Transform structured research into a compelling LinkedIn post that engineers will read, save, and share.

Style Guidelines:
- Clear, concise, slightly conversational — like a senior engineer sharing over coffee
- Every sentence earns its place — cut anything that doesn't add value
- Emojis: max 2–3 total, only where they genuinely add visual separation
- Sound like a real person with strong opinions, not a content machine

Required Structure:
1. HOOK — First line must stop the scroll: a bold claim, surprising stat, or relatable failure
2. CONTEXT — Why this matters right now (2–3 lines max)
3. INSIGHTS — Core knowledge (3–5 bullets or short punchy paragraphs)
4. TAKEAWAY — The one thing to remember, stated boldly
5. CTA — A real question that sparks comments
6. IMAGE PROMPT — A detailed prompt in English to generate a matching image (Midjourney/DALL-E style) placed at the very end.

Hard Constraints:
- 150–220 words MAX
- First line must work as a standalone hook if truncated
- No generic openers: "In today's world...", "As engineers, we...", "Have you ever..."
- No filler: "It's important to note that...", "At the end of the day..."
- No repetition of ideas across sections"""


from core.model_registry import ModelProfile

class ContentWriterAgent(BaseAgent):
    def __init__(self, router):
        super().__init__(
            system_prompt=SYSTEM_PROMPT,
            profile=ModelProfile.ECONOMY_TEXT,
            router=router
        )

    async def stream(self, idea: str, research: str, style: str, attempt_id: str = None) -> AsyncGenerator[tuple, None]:
        style_map = {
            "story": "Use a narrative structure. Start with a hook, build tension, end with a takeaway.",
            "listicle": "Use bullet points or numbered lists. Be highly actionable.",
            "opinion": "Take a strong stance on an industry topic. Defend it with facts from the research."
        }
        style_prompt = style_map.get(style, "Write in a professional but engaging tone.")

        prompt = f"""Write a LinkedIn post.

Idea: {idea}
Research context: {research}
Style constraint: {style_prompt}"""
        
        async for event in super().stream(prompt, attempt_id):
            yield event
