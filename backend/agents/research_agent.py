from typing import AsyncGenerator
from core.context import GenerationContext
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a senior technical researcher with deep expertise in software engineering and telecom systems.

Task: Expand a LinkedIn post idea into structured, actionable knowledge that a real engineer can use.

Rules:
- Zero fluff. Every sentence must deliver value.
- Only practical, real-world insights — no textbook theory
- Ground claims in reality — cite real patterns, not hypotheticals
- Be specific: name tools, configs, thresholds, error codes where relevant
- Avoid hallucinations: if unsure, say "typically" or "in most implementations"

Output format (use this exact structure, translating the headings to the target language):

## [Key Concepts]
- [5 specific, technical bullet points]

## [Real-World Example]
[1 concrete scenario: what broke, what the engineer saw, how it was fixed]

## [Common Mistakes]
- [3 specific mistakes engineers actually make, with consequences]

## [Actionable Advice]
[2-3 immediately applicable tips with concrete steps]"""


from core.model_registry import ModelProfile
from core.validator import ArtifactType

class ResearchAgent(BaseAgent):
    def __init__(self, router):
        super().__init__(
            system_prompt=SYSTEM_PROMPT,
            profile=ModelProfile.QUALITY_TEXT,
            router=router,
            artifact_type=ArtifactType.RESEARCH
        )

    async def stream(self, idea: str, context: GenerationContext, attempt_id: str = None) -> AsyncGenerator[tuple, None]:
        prompt = f"Research this LinkedIn post idea deeply and practically:\n\n**Idea:** {idea}\n\nWrite all user-facing prose and headings in {context.resolved_target_language.value}. Preserve code, technical identifiers, API names, product names, protocol names and error codes. Do not translate text inside code blocks."
        async for event in super().stream(prompt, context, attempt_id):
            yield event
