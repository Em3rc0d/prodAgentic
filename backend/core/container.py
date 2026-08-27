import os
from google import genai
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.n8n_adapter import N8nAdapter
from agents.router import ModelRouter
from agents.orchestrator import PipelineOrchestrator
from core.assets import get_render_storage_dir
from core.settings import ApplicationSettings, LEGACY_WORKSPACE_ID
import logging

logger = logging.getLogger(__name__)


class ApplicationContainer:
    def __init__(self):
        self.client = None
        self.google_adapter = None
        self.n8n_adapter = None
        self.router = None
        self.pipeline_service = None
        self.visual_service = None
        self.settings = None
        self.preflight_task = None

    def startup(self):
        self.config_error = None

        # --- Single authoritative settings load ---
        try:
            self.settings = ApplicationSettings.load()
        except ValueError as e:
            self.config_error = str(e)
            logger.error(f"[CONFIG] {e}")
            # Continue startup so health endpoint can report NOT_READY with reason

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment!")
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

        self.router = ModelRouter(
            google_adapter=self.google_adapter,
            n8n_adapter=self.n8n_adapter,
            routing_policy=routing_policy,
        )
        workspace_id = self.settings.app_workspace_id if self.settings else LEGACY_WORKSPACE_ID
        self.pipeline_service = PipelineOrchestrator(self.router, workspace_id=workspace_id)

        from agents.adapters.image import PollinationsImageAdapter
        from core.visual import VisualRenderService

        image_enabled = self.settings.image_render_enabled if self.settings else False
        provider = PollinationsImageAdapter()
        self.visual_service = VisualRenderService(
            provider,
            storage_dir=str(get_render_storage_dir()),
            image_render_enabled=image_enabled,
        )

    async def shutdown(self):
        if self.client:
            if hasattr(self.client, "aio") and hasattr(self.client.aio, "aclose"):
                try:
                    await self.client.aio.aclose()
                except Exception:
                    pass
            if hasattr(self.client, "close"):
                try:
                    self.client.close()
                except Exception:
                    pass
