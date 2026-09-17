from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from domain.rendering.ports import ImageGenerationPortError
from infrastructure.visual import gemini_image
from infrastructure.visual.gemini_image import GeminiImageGenerationAdapter


PNG = b"\x89PNG\r\n\x1a\n" + b"bounded-test-png"


@pytest.mark.asyncio
async def test_image_adapter_retries_transient_provider_failure_once(monkeypatch):
    calls = 0

    class Models:
        async def generate_content(self, *, model, contents, config):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("503 temporarily unavailable")
            return SimpleNamespace(
                parts=(
                    SimpleNamespace(
                        inline_data=SimpleNamespace(
                            mime_type="image/png",
                            data=PNG,
                        )
                    ),
                )
            )

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    adapter = GeminiImageGenerationAdapter(
        client,
        model="test-image-model",
        timeout_seconds=10.0,
    )
    monkeypatch.setattr(gemini_image, "IMAGE_RETRY_DELAY_SECONDS", 0.0)

    result = await adapter.generate(prompt="premium architecture visual", aspect_ratio="4:5")

    assert calls == 2
    assert result.data == PNG
    assert result.content_type == "image/png"


@pytest.mark.asyncio
async def test_image_adapter_does_not_retry_terminal_provider_failure(monkeypatch):
    calls = 0

    class Models:
        async def generate_content(self, *, model, contents, config):
            nonlocal calls
            calls += 1
            raise RuntimeError("400 invalid request")

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    adapter = GeminiImageGenerationAdapter(
        client,
        model="test-image-model",
        timeout_seconds=10.0,
    )
    monkeypatch.setattr(gemini_image, "IMAGE_RETRY_DELAY_SECONDS", 0.0)

    with pytest.raises(ImageGenerationPortError) as exc_info:
        await adapter.generate(prompt="premium architecture visual", aspect_ratio="4:5")

    assert calls == 1
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_image_adapter_bounds_two_timeout_attempts(monkeypatch):
    calls = 0

    class Models:
        async def generate_content(self, *, model, contents, config):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.15)
            return SimpleNamespace(parts=())

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    adapter = GeminiImageGenerationAdapter(
        client,
        model="test-image-model",
        timeout_seconds=10.0,
    )
    adapter.timeout_seconds = 0.1
    monkeypatch.setattr(gemini_image, "IMAGE_RETRY_DELAY_SECONDS", 0.0)

    with pytest.raises(ImageGenerationPortError) as exc_info:
        await adapter.generate(prompt="premium architecture visual", aspect_ratio="4:5")

    assert calls == 2
    assert exc_info.value.retryable is True
