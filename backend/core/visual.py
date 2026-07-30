import asyncio
import httpx
import uuid
import os
import logging
from pathlib import Path
from models.visual import VisualRenderRequest, VisualRenderResponse, RenderStatus
from agents.adapters.image import ImageRenderProvider

logger = logging.getLogger(__name__)

class CircuitBreakerOpen(Exception):
    pass

class VisualRenderService:
    def __init__(self, provider: ImageRenderProvider, storage_dir: str = "static/assets/renders"):
        self.provider = provider
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Idempotency store (in-memory for now)
        self._idempotency_store = {}
        
        # Circuit breaker settings
        self.failure_count = 0
        self.max_failures = 3
        self.circuit_open_until = 0
        self.kill_switch_active = False

    async def render(self, req: VisualRenderRequest) -> VisualRenderResponse:
        if self.kill_switch_active:
            return self._failed_response("Visual rendering is currently disabled.", req)
            
        import time
        if time.time() < self.circuit_open_until:
            return self._failed_response("Visual rendering service temporarily unavailable.", req)
            
        if req.idempotency_key in self._idempotency_store:
            return self._idempotency_store[req.idempotency_key]
            
        render_id = str(uuid.uuid4())
        
        try:
            # 1. Trigger render from provider
            result = await self.provider.render(req.prompt, req.aspect_ratio.value, req.style.value)
            
            # 2. Fetch the actual image bytes with timeout and retries
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await self._fetch_with_retries(client, result.url)
                resp.raise_for_status()
                image_bytes = resp.content
                
            # 3. Persist asset
            filename = f"{render_id}.png"
            file_path = self.storage_dir / filename
            file_path.write_bytes(image_bytes)
            
            asset_url = f"/assets/renders/{filename}"
            
            # Reset circuit breaker
            self.failure_count = 0
            
            response = VisualRenderResponse(
                render_id=render_id,
                status=RenderStatus.READY,
                provider=self.provider.__class__.__name__,
                asset_url=asset_url,
                width=800, # Mocked width, could be parsed from provider response
                height=400 if req.aspect_ratio.value in ("16:9", "2:1") else 800,
                prompt_used=result.prompt_used
            )
            
            self._idempotency_store[req.idempotency_key] = response
            return response
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
            self.failure_count += 1
            if self.failure_count >= self.max_failures:
                self.circuit_open_until = time.time() + 60 # Open circuit for 60 seconds
            
            return self._failed_response("Failed to generate or fetch image.", req)
            
    async def _fetch_with_retries(self, client, url: str, max_retries: int = 2):
        last_exception = None
        for attempt in range(max_retries):
            try:
                return await client.get(url)
            except Exception as e:
                last_exception = e
                await asyncio.sleep(2 ** attempt)
        raise last_exception

    def _failed_response(self, error_msg: str, req: VisualRenderRequest) -> VisualRenderResponse:
        return VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider=self.provider.__class__.__name__,
            prompt_used=req.prompt,
            error_message=error_msg
        )
