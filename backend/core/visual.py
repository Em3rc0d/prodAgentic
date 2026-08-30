import asyncio
import base64
import binascii
import hashlib
import httpx
import struct
import uuid
import time
import logging
from pathlib import Path
from models.visual import VisualRenderRequest, VisualRenderResponse, RenderStatus
from agents.adapters.image import ImageRenderProvider

logger = logging.getLogger(__name__)

# Guardrail constants
MAX_PROMPT_BYTES = 2048
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_LINKEDIN_PIXELS = 36_152_320
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_CONCURRENT_RENDERS = 4
FETCH_TIMEOUT_SECONDS = 30.0

_RATIO_VALUES = {
    "1:1": 1.0,
    "4:5": 4 / 5,
    "16:9": 16 / 9,
}


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

        # This switch controls external/generative image rendering only.
        # Deterministic browser-rendered PNGs remain available because they do
        # not call an external image provider.
        self.kill_switch_active = not image_render_enabled

        # Each key is permanently bound to one render intent. Deterministic
        # renders include their byte digest in the signature so a caller cannot
        # reuse the same key with different PNG bytes.
        self._idempotency_store: dict[
            str,
            tuple[tuple[str, str, str, str], VisualRenderResponse],
        ] = {}

        self.failure_count = 0
        self.max_failures = 3
        self.circuit_open_until: float = 0.0
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_RENDERS)

    @staticmethod
    def _intent_signature(
        req: VisualRenderRequest,
        *,
        deterministic_digest: str | None = None,
    ) -> tuple[str, str, str, str]:
        mode = deterministic_digest or "GENERATIVE"
        return (req.prompt, req.aspect_ratio.value, req.style.value, mode)

    def _cached_or_conflict(
        self,
        req: VisualRenderRequest,
        signature: tuple[str, str, str, str],
    ) -> VisualRenderResponse | None:
        cached = self._idempotency_store.get(req.idempotency_key)
        if cached is None:
            return None
        cached_signature, cached_response = cached
        if cached_signature != signature:
            return self._failed_response(
                "Idempotency key is already bound to a different render request.",
                req,
            )
        return cached_response

    async def render(self, req: VisualRenderRequest) -> VisualRenderResponse:
        """Render through the external image provider.

        HYBRID-VISUAL-01 routes only server-selected illustration formats here.
        Technical/editorial layouts use ``render_deterministic`` instead.
        """
        if self.kill_switch_active:
            return self._failed_response("Image rendering is disabled (IMAGE_RENDER_ENABLED=false).", req)

        if time.time() < self.circuit_open_until:
            return self._failed_response(
                "Image rendering temporarily unavailable (circuit open).", req
            )

        signature = self._intent_signature(req)
        cached = self._cached_or_conflict(req, signature)
        if cached is not None:
            return cached

        if not req.prompt or not req.prompt.strip():
            return self._failed_response("Prompt must not be empty.", req)
        if len(req.prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            return self._failed_response(
                f"Prompt exceeds maximum length of {MAX_PROMPT_BYTES} bytes.", req
            )

        render_id = str(uuid.uuid4())

        async with self._semaphore:
            try:
                result = await self.provider.render(req.prompt, req.aspect_ratio.value, req.style.value)
                image_bytes = await self._fetch_image(result.url)

                filename = f"{render_id}.png"
                file_path = self.storage_dir / filename
                file_path.write_bytes(image_bytes)

                asset_url = f"/assets/renders/{filename}"
                asset_sha256 = hashlib.sha256(image_bytes).hexdigest()
                self.failure_count = 0

                response = VisualRenderResponse(
                    render_id=render_id,
                    status=RenderStatus.READY,
                    provider=self.provider.__class__.__name__,
                    asset_url=asset_url,
                    asset_sha256=asset_sha256,
                    width=result.width,
                    height=result.height,
                    prompt_used=result.prompt_used,
                )

                self._idempotency_store[req.idempotency_key] = (signature, response)
                return response

            except Exception as e:
                logger.error(f"Render failed for render_id={render_id}: {e}")
                self.failure_count += 1
                if self.failure_count >= self.max_failures:
                    self.circuit_open_until = time.time() + 60
                    logger.warning("Circuit breaker OPEN — visual rendering suspended for 60s")

                return self._failed_response(str(e), req)

    async def render_deterministic(self, req: VisualRenderRequest) -> VisualRenderResponse:
        """Persist a browser-rasterized deterministic editorial layout.

        The browser is used only as a rasterizer. Server code validates the PNG
        signature, declared SHA-256, pixel dimensions and requested aspect ratio
        before accepting bytes into the owned asset boundary.
        """
        if not req.deterministic_png_base64 or not req.deterministic_png_sha256:
            return self._failed_response(
                "Deterministic visual requires PNG bytes and SHA-256 digest.",
                req,
                provider="DeterministicBrowserRenderer",
            )

        try:
            image_bytes = base64.b64decode(req.deterministic_png_base64, validate=True)
        except (binascii.Error, ValueError):
            return self._failed_response(
                "Deterministic visual payload is not valid base64.",
                req,
                provider="DeterministicBrowserRenderer",
            )

        if len(image_bytes) > MAX_DOWNLOAD_BYTES:
            return self._failed_response(
                f"Deterministic PNG exceeds {MAX_DOWNLOAD_BYTES // (1024 * 1024)}MB limit.",
                req,
                provider="DeterministicBrowserRenderer",
            )

        actual_digest = hashlib.sha256(image_bytes).hexdigest()
        expected_digest = req.deterministic_png_sha256.lower()
        if actual_digest != expected_digest:
            return self._failed_response(
                "Deterministic PNG byte digest does not match declared SHA-256.",
                req,
                provider="DeterministicBrowserRenderer",
            )

        try:
            width, height = self._png_dimensions(image_bytes)
            self._validate_dimensions(width, height, req.aspect_ratio.value)
        except ValueError as exc:
            return self._failed_response(
                str(exc),
                req,
                provider="DeterministicBrowserRenderer",
            )

        signature = self._intent_signature(req, deterministic_digest=actual_digest)
        cached = self._cached_or_conflict(req, signature)
        if cached is not None:
            return cached

        render_id = str(uuid.uuid4())
        filename = f"{render_id}.png"
        file_path = self.storage_dir / filename
        file_path.write_bytes(image_bytes)

        response = VisualRenderResponse(
            render_id=render_id,
            status=RenderStatus.READY,
            provider="DeterministicBrowserRenderer",
            asset_url=f"/assets/renders/{filename}",
            asset_sha256=actual_digest,
            width=width,
            height=height,
            prompt_used=req.prompt,
        )
        self._idempotency_store[req.idempotency_key] = (signature, response)
        return response

    @staticmethod
    def _png_dimensions(data: bytes) -> tuple[int, int]:
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Deterministic visual must be a PNG image.")
        if data[12:16] != b"IHDR":
            raise ValueError("Deterministic PNG has no valid IHDR header.")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise ValueError("Deterministic PNG has invalid dimensions.")
        return width, height

    @staticmethod
    def _validate_dimensions(width: int, height: int, aspect_ratio: str) -> None:
        if width * height > MAX_LINKEDIN_PIXELS:
            raise ValueError("Deterministic PNG exceeds LinkedIn image pixel limit.")
        expected = _RATIO_VALUES[aspect_ratio]
        actual = width / height
        if abs(actual - expected) > 0.015:
            raise ValueError(
                f"Deterministic PNG aspect ratio {width}:{height} does not match requested {aspect_ratio}."
            )

    async def _fetch_image(self, url: str) -> bytes:
        """Fetch image with timeout, retry on 429/5xx, Content-Type and size guards."""
        last_exception: Exception | None = None

        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url)

                    if resp.status_code == 429 or resp.status_code >= 500:
                        logger.warning(f"HTTP {resp.status_code} on attempt {attempt + 1}, retrying…")
                        await asyncio.sleep(2 ** attempt)
                        continue

                    resp.raise_for_status()

                    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                    if content_type not in ALLOWED_CONTENT_TYPES:
                        logger.warning(f"Unexpected content-type: {content_type!r}")

                    content = resp.content
                    if len(content) > MAX_DOWNLOAD_BYTES:
                        raise ValueError(
                            f"Response exceeds {MAX_DOWNLOAD_BYTES // (1024*1024)}MB limit"
                        )

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
        if len(data) < 4:
            return False
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if data[:2] == b"\xff\xd8":
            return True
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return True
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return True
        return False

    def _failed_response(
        self,
        error_msg: str,
        req: VisualRenderRequest,
        *,
        provider: str | None = None,
    ) -> VisualRenderResponse:
        return VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider=provider or self.provider.__class__.__name__,
            prompt_used=req.prompt,
            error_message=error_msg,
        )
