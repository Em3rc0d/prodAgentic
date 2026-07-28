import os
from google import genai
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.n8n_adapter import N8nAdapter
from agents.router import ModelRouter
from agents.orchestrator import PipelineOrchestrator
import logging

class ApplicationContainer:
    def __init__(self):
        self.client = None
        self.google_adapter = None
        self.n8n_adapter = None
        self.router = None
        self.pipeline_service = None
        self.preflight_task = None

    def startup(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.error("GEMINI_API_KEY not found in environment!")
            
        self.client = genai.Client(api_key=api_key)
        self.google_adapter = GoogleDirectAdapter(self.client)
        
        from agents.router import RoutingPolicy
        RoutingPolicy.allow_direct_provider_fallback_after_n8n_failure = os.getenv("N8N_ALLOW_DIRECT_FALLBACK", "false").lower() == "true"
        
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if n8n_webhook_url and "your-domain" not in n8n_webhook_url:
            self.n8n_adapter = N8nAdapter(n8n_webhook_url)
        else:
            self.n8n_adapter = None
            
        self.router = ModelRouter(self.google_adapter, self.n8n_adapter)
        self.pipeline_service = PipelineOrchestrator(self.router)

    async def shutdown(self):
        if self.client:
            if hasattr(self.client, 'aio') and hasattr(self.client.aio, 'aclose'):
                await self.client.aio.aclose()
            elif hasattr(self.client, 'close'):
                self.client.close()
