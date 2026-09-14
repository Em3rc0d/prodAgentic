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
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise ImageGenerationPortError("image provider timed out", retryable=True) from exc
        except Exception as exc:
            message = str(exc).lower()
            retryable = any(token in message for token in ("429", "rate", "timeout", "503", "unavailable"))
            raise ImageGenerationPortError("image provider request failed", retryable=retryable) from exc

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
