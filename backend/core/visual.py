import asyncio
import httpx
import uuid
import os
import time
import logging
from pathlib import Path
from models.visual import VisualRenderRequest, VisualRenderResponse, RenderStatus
from agents.adapters.image import ImageRenderProvider

logger = logging.getLogger(__name__)

# Guardrail constants
MAX_PROMPT_BYTES = 2048
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_CONCURRENT_RENDERS = 4
FETCH_TIMEOUT_SECONDS = 30.0


class VisualRenderService:
    def __init__(
        self,
        provider: ImageRenderProvider,
        storage_dir: str = "static/assets/renders",
        image_render_enabled: bool = True,
    ):
        self.provider = provider
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # kill switch — env-controlled or passed at construction
        self.kill_switch_active = not image_render_enabled

        # Idempotency store (in-memory; replace with Redis for multi-worker)
        self._idempotency_store: dict[str, VisualRenderResponse] = {}

        # Circuit breaker
        self.failure_count = 0
        self.max_failures = 3
        self.circuit_open_until: float = 0.0

        # Concurrency semaphore
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_RENDERS)

    async def render(self, req: VisualRenderRequest) -> VisualRenderResponse:
        # Kill switch
        if self.kill_switch_active:
            return self._failed_response("Image rendering is disabled (IMAGE_RENDER_ENABLED=false).", req)

        # Circuit breaker
        if time.time() < self.circuit_open_until:
            return self._failed_response(
                "Image rendering temporarily unavailable (circuit open).", req
            )

        # Idempotency
        if req.idempotency_key in self._idempotency_store:
            return self._idempotency_store[req.idempotency_key]

        # Prompt length guardrail
        if not req.prompt or not req.prompt.strip():
            return self._failed_response("Prompt must not be empty.", req)
        if len(req.prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            return self._failed_response(
                f"Prompt exceeds maximum length of {MAX_PROMPT_BYTES} bytes.", req
            )

        render_id = str(uuid.uuid4())

        async with self._semaphore:
            try:
                # 1. Trigger render from provider
                result = await self.provider.render(req.prompt, req.aspect_ratio.value, req.style.value)

                # 2. Fetch image bytes with guardrails
                image_bytes = await self._fetch_image(result.url)

                # 3. Persist asset
                filename = f"{render_id}.png"
                file_path = self.storage_dir / filename
                file_path.write_bytes(image_bytes)

                asset_url = f"/assets/renders/{filename}"

                # Reset circuit breaker on success
                self.failure_count = 0

                response = VisualRenderResponse(
                    render_id=render_id,
                    status=RenderStatus.READY,
                    provider=self.provider.__class__.__name__,
                    asset_url=asset_url,
                    width=result.width,
                    height=result.height,
                    prompt_used=result.prompt_used,
                )

                self._idempotency_store[req.idempotency_key] = response
                return response

            except Exception as e:
                logger.error(f"Render failed for render_id={render_id}: {e}")
                self.failure_count += 1
                if self.failure_count >= self.max_failures:
                    self.circuit_open_until = time.time() + 60
                    logger.warning("Circuit breaker OPEN — visual rendering suspended for 60s")

                return self._failed_response(str(e), req)

    async def _fetch_image(self, url: str) -> bytes:
        """Fetch image with timeout, retry on 429/5xx, Content-Type and size guards."""
        last_exception: Exception | None = None

        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            for attempt in range(3):  # 1 initial + 2 retries
                try:
                    resp = await client.get(url)

                    # Retry on 429 or 5xx
                    if resp.status_code == 429 or resp.status_code >= 500:
                        logger.warning(f"HTTP {resp.status_code} on attempt {attempt + 1}, retrying…")
                        await asyncio.sleep(2 ** attempt)
                        continue

                    resp.raise_for_status()

                    # Content-Type guard
                    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                    if content_type not in ALLOWED_CONTENT_TYPES:
                        # Pollinations doesn't always return correct headers — skip strict check
                        # but log it
                        logger.warning(f"Unexpected content-type: {content_type!r}")

                    # Size guard
                    content = resp.content
                    if len(content) > MAX_DOWNLOAD_BYTES:
                        raise ValueError(
                            f"Response exceeds {MAX_DOWNLOAD_BYTES // (1024*1024)}MB limit"
                        )

                    # Basic image magic-bytes check
                    if not self._looks_like_image(content):
                        raise ValueError("Response bytes do not match any known image format")

                    return content

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_exception = e
                    logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(2 ** attempt)

        raise last_exception or RuntimeError("Exhausted retries fetching image")

    @staticmethod
    def _looks_like_image(data: bytes) -> bool:
        """Check magic bytes for common image formats."""
        if len(data) < 4:
            return False
        # PNG
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        # JPEG
        if data[:2] == b"\xff\xd8":
            return True
        # WebP
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return True
        # GIF
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return True
        return False

    def _failed_response(self, error_msg: str, req: VisualRenderRequest) -> VisualRenderResponse:
        return VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider=self.provider.__class__.__name__,
            prompt_used=req.prompt,
            error_message=error_msg,
        )
