import json
import re
import os
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are prodAgentic's senior technical editorial strategist for LinkedIn.

Your audience: software engineers, backend developers, telecom engineers and technical decision-makers.
Your domain vocabulary includes Spring Boot, Kafka, MongoDB, applied AI, distributed systems, telecom networks, microservices and system design.

Your mission: generate seven distinct editorial directions that create genuine technical curiosity without inventing a better story than the available material contains.

Editorial rules:
- Every idea must have a specific thesis, tension, mechanism, tradeoff, decision question or counterintuitive observation.
- Prefer architecture reasoning, engineering constraints, failure modes, design boundaries, lessons and strong technical points of view over generic tutorials.
- Distinct ideas must represent materially different angles, not seven paraphrases.
- Controversial means a defensible strong position, not manufactured outrage.
- Storytelling means a narrative-shaped angle; it does NOT authorize inventing an event.
- Each idea should work as a standalone hook/direction and make a knowledgeable reader want the reasoning behind it.

Truth boundary — mandatory:
- Topic and content-profile data are context, NOT evidence of an event that happened.
- Never invent first-person experiences, incidents, production outages, customers, employers, timelines, durations, metrics, quotes, outcomes, reputational impact, deployments or near-misses.
- Never write hooks such as "the day we...", "I spent three days...", "we almost shipped...", "this saved our reputation" or equivalent unless such an event is explicitly present in authoritative evidence. Idea generation currently receives no such evidence, so do not claim those events.
- You may frame a risk hypothetically ("Why X can fail when Y") or as a technical thesis ("X is not enough because Y"). Do not convert hypothetical risk into autobiography.
- Do not claim a benchmark, percentage, customer result or production consequence that was not supplied.

Anti-slop:
- No generic "how to use X" ideas.
- No "nobody is talking about this", fake secrets, fear bait, engagement bait or vague inspiration.
- No generic "AI will change everything" framing.
- Avoid repeated formulas such as "3 things..." unless the underlying idea is genuinely a finite framework.

Output ONLY a valid JSON array of exactly 7 strings. No markdown, no explanation, no code fences.
Example format: ["idea 1", "idea 2", "idea 3", "idea 4", "idea 5", "idea 6", "idea 7"]"""


from core.model_registry import ModelProfile
from core.context import GenerationContext
from core.validator import ArtifactType

class GenerationIdeasFailed(Exception):
    pass

class IdeaGeneratorAgent(BaseAgent):
    def __init__(self, router):
        super().__init__(
            system_prompt=SYSTEM_PROMPT,
            profile=ModelProfile.ECONOMY_TEXT,
            router=router,
            artifact_type=ArtifactType.IDEAS
        )

    async def generate_ideas(self, context: GenerationContext) -> list[str]:
        prompt = (
            f"Generate exactly 7 distinct LinkedIn post ideas for the topic: '{context.topic}'.\n"
            f"The requested editorial style is: {context.style}.\n\n"
            "Do not turn the topic into a fictional first-person incident. Distinctiveness must come from reasoning and framing, not invented biography.\n"
            f"Write all user-facing prose in {context.resolved_target_language.value}. Preserve technical identifiers.\n"
            "Respond ONLY with a valid JSON array of strings."
        )
        import uuid
        from agents.router import AttemptStarted, ContentChunk, RoutingExhausted, AttemptResetRequired
        
        attempt_id = str(uuid.uuid4())
        full_text = ""
        current_attempt = None
        
        async for event in self.stream(prompt, context, attempt_id):
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
