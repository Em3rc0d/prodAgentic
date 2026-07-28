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

class GenerationIdeasFailed(Exception):
    pass

class IdeaGeneratorAgent(BaseAgent):
    def __init__(self, router):
        super().__init__(
            system_prompt=SYSTEM_PROMPT,
            profile=ModelProfile.ECONOMY_TEXT,
            router=router
        )

    async def generate_ideas(self, topic: str, style: str) -> list[str]:
        prompt = (
            f"Generate exactly 7 distinct LinkedIn post ideas for the topic: '{topic}'.\n"
            f"The style should be: {style}.\n\n"
            "Respond ONLY with a valid JSON array of strings."
        )
        import uuid
        from agents.router import AttemptStarted, ContentChunk, RoutingExhausted, AttemptResetRequired
        
        attempt_id = str(uuid.uuid4())
        full_text = ""
        current_attempt = None
        
        async for event in self.stream(prompt, attempt_id):
            if isinstance(event, AttemptStarted):
                current_attempt = event.attempt_id
                full_text = ""
            elif isinstance(event, AttemptResetRequired):
                full_text = ""
            elif isinstance(event, ContentChunk):
                if event.attempt_id == current_attempt:
                    full_text += event.text
            elif isinstance(event, RoutingExhausted):
                raise GenerationIdeasFailed(f"Failed to generate ideas: {event.reason}")
                
        try:
            import re
            import json
            cleaned_text = re.sub(r"```json\n|\n```|```", "", full_text).strip()
            
            ideas = json.loads(cleaned_text)
            if not isinstance(ideas, list):
                raise GenerationIdeasFailed("Output is not a JSON array")
            
            valid_ideas = [i.strip() for i in ideas if isinstance(i, str) and i.strip()]
            if len(valid_ideas) != 7:
                raise GenerationIdeasFailed(f"Expected 7 valid ideas, got {len(valid_ideas)}")
                
            return valid_ideas
        except json.JSONDecodeError as e:
            print(f"[ERROR] Idea generator JSON decode error. Text was: {full_text}")
            raise GenerationIdeasFailed(f"JSON parsing error: {e}")
