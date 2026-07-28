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


class IdeaGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(SYSTEM_PROMPT)

    def generate_ideas(self, topic: str, style: str) -> list[str]:
        prompt = (
            f"Generate 7 viral LinkedIn post ideas about: {topic}\n"
            f"Writing style preference: {style}\n\n"
            f"Return ONLY the JSON array of 7 strings."
        )
        raw = self.generate(prompt)

        # Robust JSON extraction
        try:
            import json
            import re
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(raw.strip())
        except Exception:
            # Fallback: parse line by line
            lines = [
                l.strip().strip('"').strip("'").strip("- ").strip()
                for l in raw.split("\n")
                if l.strip()
            ]
            return [l for l in lines if len(l) > 15][:7]
