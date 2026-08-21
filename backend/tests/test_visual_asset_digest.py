import hashlib

import pytest

from agents.adapters.image import ImageRenderProvider, ImageRenderResult
from core.visual import VisualRenderService
from models.visual import RenderStatus, VisualRenderRequest


class DigestProvider(ImageRenderProvider):
    async def render(self, prompt: str, aspect_ratio: str = "16:9", style: str = "") -> ImageRenderResult:
        return ImageRenderResult(
            url="https://example.test/render.png",
            prompt_used=prompt,
            aspect_ratio=aspect_ratio,
            width=1200,
            height=675,
        )


@pytest.mark.asyncio
async def test_ready_render_digest_matches_persisted_image_bytes(tmp_path):
    image_bytes = b"\x89PNG\r\n\x1a\nprod-agentic-approved-evidence"
    service = VisualRenderService(DigestProvider(), storage_dir=str(tmp_path))

    async def fake_fetch(_url: str) -> bytes:
        return image_bytes

    service._fetch_image = fake_fetch

    result = await service.render(VisualRenderRequest(
        run_id="run-digest",
        idempotency_key="digest-key-1234",
        prompt="approved visual",
    ))

    assert result.status == RenderStatus.READY
    assert result.asset_sha256 == hashlib.sha256(image_bytes).hexdigest()
    persisted = tmp_path / f"{result.render_id}.png"
    assert persisted.read_bytes() == image_bytes
