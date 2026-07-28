import os
import uuid
from typing import AsyncGenerator
from core.model_registry import ModelProfile
from agents.router import ModelRouter

class BaseAgent:
    def __init__(self, system_prompt: str, profile: ModelProfile, router: ModelRouter):
        self.system_prompt = system_prompt
        self.profile = profile
        self.router = router

    async def stream(self, prompt: str, attempt_id: str = None, run_id: str = "default-run") -> AsyncGenerator[tuple, None]:
        """Yields domain events from the router."""
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
            
        async for event in self.router.stream_generation(self.profile, self.system_prompt, prompt, run_id):
            yield event

    async def generate(self, prompt: str, attempt_id: str = None, run_id: str = "default-run") -> tuple:
        """Asynchronous generation. Returns (actual_model, text)."""
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
            
        return await self.router.generate(self.profile, self.system_prompt, prompt, run_id)

