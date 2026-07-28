import os
import uuid
from typing import AsyncGenerator
from google import genai
from dotenv import load_dotenv
from core.model_registry import ModelProfile
from agents.router import ModelRouter, StageFailedException
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.n8n_adapter import N8nAdapter

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in environment!")
else:
    print(f"[DEBUG] Gemini Client initialized with key: {api_key[:8]}...")

# Global Router Instance with Adapters
client = genai.Client(api_key=api_key)
google_adapter = GoogleDirectAdapter(client)
n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
n8n_adapter = N8nAdapter(n8n_webhook_url) if n8n_webhook_url and "your-domain" not in n8n_webhook_url else None

router = ModelRouter(google_adapter=google_adapter, n8n_adapter=n8n_adapter)

class BaseAgent:
    def __init__(self, system_prompt: str, profile: ModelProfile):
        self.system_prompt = system_prompt
        self.profile = profile

    async def stream(self, prompt: str, attempt_id: str = None) -> AsyncGenerator[tuple, None]:
        """Yields ('model_selected', model_id) and ('chunk', text)."""
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
            
        async for event in router.stream_generation(self.profile, self.system_prompt, prompt, attempt_id):
            yield event

    async def generate(self, prompt: str, attempt_id: str = None) -> tuple:
        """Asynchronous generation. Returns (actual_model, text)."""
        if not attempt_id:
            attempt_id = str(uuid.uuid4())
            
        return await router.generate(self.profile, self.system_prompt, prompt, attempt_id)
