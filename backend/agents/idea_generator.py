import json
import re
import os
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a senior content strategist specialized in technical LinkedIn content.

Your audience: software engineers, backend developers, telecom engineers.
Your topics expertise: Spring Boot, Kafka, MongoDB, AI, distributed systems, telecom networks, microservices.

Your mission: Generate high-engagement LinkedIn post ideas that make engineers stop scrolling.

Rules:
- Every idea must be SPECIFIC — not "how to use Kafka" but "Why Kafka consumers silently lag and kill your SLAs"
- Focus on real-world pain points, surprising insights, or counterintuitive lessons
- Include controversy, strong opinions, or a twist
- Avoid clichés: no "In today's fast-paced world" or "leverage synergies"
- Each idea must work as a standalone hook sentence

Output ONLY a valid JSON array of exactly 7 strings. No markdown, no explanation, no code fences.
Example format: ["idea 1", "idea 2", "idea 3", "idea 4", "idea 5", "idea 6", "idea 7"]"""


from core.model_registry import ModelProfile

class IdeaGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(SYSTEM_PROMPT, ModelProfile.ECONOMY_TEXT)

    async def generate_ideas(self, topic: str, style: str) -> list[str]:
        prompt = (
            f"Generate exactly 7 distinct LinkedIn post ideas for the topic: '{topic}'.\n"
            f"The style should be: {style}.\n\n"
            "Respond ONLY with a valid JSON array of strings."
        )
        try:
            import uuid
            attempt_id = str(uuid.uuid4())
            actual_model, text = await self.generate(prompt, attempt_id)
            import re
            cleaned_text = re.sub(r"```json\n|\n```|```", "", text).strip()
            
            import json
            ideas = json.loads(cleaned_text)
            if isinstance(ideas, list):
                return ideas
            else:
                return [cleaned_text]
        except Exception as e:
            print(f"[WARN] Idea generation failed: {e}")
            return [
                "1. Focus on core architectural decisions and their trade-offs.",
                "2. Share a specific failure story and the technical lessons learned.",
                "3. Explain a complex system component using simple analogies.",
                "4. Compare two competing technologies objectively.",
                "5. Write a mini-case study of an optimization that improved performance."
            ][:7]
