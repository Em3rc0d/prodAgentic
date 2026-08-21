import uuid
from typing import AsyncGenerator

from core.model_registry import ModelProfile
from core.context import GenerationContext
from core.validator import ArtifactType
from agents.router import ModelRouter, ModelExecutionRequest


class BaseAgent:
    def __init__(self, system_prompt: str, profile: ModelProfile, router: ModelRouter, artifact_type: ArtifactType):
        self.system_prompt = system_prompt
        self.profile = profile
        self.router = router
        self.artifact_type = artifact_type

    async def stream(self, prompt: str, context: GenerationContext, attempt_id: str = None) -> AsyncGenerator[tuple, None]:
        """Yields domain events from the router."""
        if not attempt_id:
            attempt_id = str(uuid.uuid4())

        expected_lang = context.image_prompt_language if self.artifact_type == ArtifactType.VISUAL else context.resolved_target_language
        profile_instructions = context.profile_instructions()
        system_instruction = self.system_prompt
        if profile_instructions:
            system_instruction = f"{system_instruction}\n\n{profile_instructions}"

        request = ModelExecutionRequest(
            context=context,
            model_profile=self.profile,
            artifact_type=self.artifact_type,
            system_instruction=system_instruction,
            user_prompt=prompt,
            expected_output_language=expected_lang,
        )

        async for event in self.router.stream_generation(request):
            yield event
