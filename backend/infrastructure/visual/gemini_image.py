from __future__ import annotations

import asyncio
import base64
import os

from google.genai import types

from domain.rendering.ports import GeneratedImageBytes, ImageGenerationPortError


_MAX_PROMPT_CHARS = 6_000
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
_ALLOWED_ASPECTS = {"1:1", "4:5", "16:9", "9:16"}

# Real-provider UAT showed transient provider failures can occur before the
# compositor is reached. Keep retries bounded here so a single high-demand spike
# does not force a human restart, while preserving an overall finite image wall.
IMAGE_MAX_ATTEMPTS = 2
IMAGE_RETRY_DELAY_SECONDS = 3.0
IMAGE_MAX_TOTAL_SECONDS = 180.0


class GeminiImageGenerationAdapter:
    """Direct-byte Gemini image adapter with no remote URL authority.

    The provider response is accepted only when it contains one bounded image
    payload with a supported MIME type and matching magic bytes. Callers persist
    and hash the returned bytes before they may enter the Chromium compositor.
    """

    provider = "google"

    def __init__(self, client, *, model: str | None = None, timeout_seconds: float = 90.0):
        self.client = client
        self.model = (model or os.getenv("PRODAGENTIC_IMAGE_MODEL") or "gemini-3.1-flash-image").strip()
        self.timeout_seconds = max(10.0, min(float(timeout_seconds), 180.0))

    async def generate(self, *, prompt: str, aspect_ratio: str) -> GeneratedImageBytes:
        value = prompt.strip()
        if not value:
            raise ImageGenerationPortError("generated image prompt cannot be blank")
        if len(value) > _MAX_PROMPT_CHARS:
            raise ImageGenerationPortError("generated image prompt exceeds bounded size")
        if aspect_ratio not in _ALLOWED_ASPECTS:
            raise ImageGenerationPortError("unsupported generated image aspect ratio")

        loop = asyncio.get_running_loop()
        total_seconds = min(
            IMAGE_MAX_TOTAL_SECONDS,
            self.timeout_seconds * IMAGE_MAX_ATTEMPTS
            + IMAGE_RETRY_DELAY_SECONDS * max(0, IMAGE_MAX_ATTEMPTS - 1),
        )
        deadline = loop.time() + total_seconds

        for attempt_index in range(IMAGE_MAX_ATTEMPTS):
            remaining = deadline - loop.time()
            has_retry = attempt_index + 1 < IMAGE_MAX_ATTEMPTS
            reserve = (
                IMAGE_RETRY_DELAY_SECONDS
                if has_retry and remaining > IMAGE_RETRY_DELAY_SECONDS + 0.05
                else 0.0
            )
            seconds = min(self.timeout_seconds, max(0.0, remaining - reserve))
            if seconds <= 0:
                raise ImageGenerationPortError("image provider timed out", retryable=True)

            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=value,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                        ),
                    ),
                    timeout=seconds,
                )
                break
            except TimeoutError as exc:
                if has_retry and deadline - loop.time() > IMAGE_RETRY_DELAY_SECONDS + 0.05:
                    await asyncio.sleep(IMAGE_RETRY_DELAY_SECONDS)
                    continue
                raise ImageGenerationPortError("image provider timed out", retryable=True) from exc
            except Exception as exc:
                message = str(exc).lower()
                status = getattr(exc, "code", None)
                retryable = status in {429, 500, 502, 503, 504} or any(
                    token in message
                    for token in (
                        "429",
                        "rate",
                        "timeout",
                        "500",
                        "502",
                        "503",
                        "504",
                        "unavailable",
                        "resource exhausted",
                        "temporarily",
                    )
                )
                if retryable and has_retry and deadline - loop.time() > IMAGE_RETRY_DELAY_SECONDS + 0.05:
                    await asyncio.sleep(IMAGE_RETRY_DELAY_SECONDS)
                    continue
                raise ImageGenerationPortError("image provider request failed", retryable=retryable) from exc
        else:  # pragma: no cover - the loop either returns a response or raises.
            raise ImageGenerationPortError("image provider request failed", retryable=True)

        for part in getattr(response, "parts", ()) or ():
            inline = getattr(part, "inline_data", None)
            if inline is None:
                continue
            content_type = (getattr(inline, "mime_type", None) or "image/png").lower().strip()
            if content_type not in _ALLOWED_TYPES:
                raise ImageGenerationPortError("image provider returned unsupported content type")
            raw = getattr(inline, "data", None)
            if raw is None:
                continue
            try:
                data = base64.b64decode(raw, validate=True) if isinstance(raw, str) else bytes(raw)
            except Exception as exc:
                raise ImageGenerationPortError("image provider returned malformed bytes") from exc
            self._validate_bytes(data, content_type)
            return GeneratedImageBytes(
                data=data,
                content_type=content_type,
                provider=self.provider,
                model=self.model,
            )
        raise ImageGenerationPortError("image provider completed without image bytes")

    @staticmethod
    def _validate_bytes(data: bytes, content_type: str) -> None:
        if not data:
            raise ImageGenerationPortError("image provider returned empty bytes")
        if len(data) > _MAX_IMAGE_BYTES:
            raise ImageGenerationPortError("image provider output exceeds bounded byte size")
        valid = False
        if content_type == "image/png":
            valid = data.startswith(b"\x89PNG\r\n\x1a\n")
        elif content_type == "image/jpeg":
            valid = data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")
        elif content_type == "image/webp":
            valid = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        if not valid:
            raise ImageGenerationPortError("image provider MIME type does not match returned bytes")
