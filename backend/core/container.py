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
        self.visual_service = None
        self.preflight_task = None

    def startup(self):
        from core.context import LanguageCode
        
        self.config_error = None
        default_lang_str = os.getenv("APP_DEFAULT_LANGUAGE", "es")
        try:
            LanguageCode(default_lang_str)
        except ValueError:
            self.config_error = f"Invalid APP_DEFAULT_LANGUAGE: {default_lang_str}"
            logging.error(self.config_error)
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.error("GEMINI_API_KEY not found in environment!")
            self.client = None
            self.google_adapter = None
        else:
            self.client = genai.Client(api_key=api_key)
            self.google_adapter = GoogleDirectAdapter(self.client)
        
        from agents.router import ModelRouter, RoutingPolicy
        
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if n8n_webhook_url and "your-domain" not in n8n_webhook_url:
            self.n8n_adapter = N8nAdapter(n8n_webhook_url)
        else:
            self.n8n_adapter = None
        
        n8n_fallback = os.getenv("N8N_ALLOW_DIRECT_FALLBACK", "").lower()
        routing_policy = RoutingPolicy()
        routing_policy.allow_direct_provider_fallback_after_n8n_failure = n8n_fallback in ("true", "1")
        
        # Instantiate ModelRouter with policy
        self.router = ModelRouter(google_adapter=self.google_adapter, n8n_adapter=self.n8n_adapter, routing_policy=routing_policy)
        self.pipeline_service = PipelineOrchestrator(self.router)

        from agents.adapters.image import PollinationsImageAdapter
        from core.visual import VisualRenderService
        self.visual_service = VisualRenderService(PollinationsImageAdapter())

    async def shutdown(self):
        if self.client:
            if hasattr(self.client, 'aio') and hasattr(self.client.aio, 'aclose'):
                try:
                    await self.client.aio.aclose()
                except Exception:
                    pass
            if hasattr(self.client, 'close'):
                try:
                    self.client.close()
                except Exception:
                    pass
