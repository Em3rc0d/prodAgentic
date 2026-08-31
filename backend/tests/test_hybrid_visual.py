import base64
import binascii
import hashlib
import struct
import zlib

import pytest

from core.visual import VisualRenderService
from models.visual import AspectRatio, RenderStatus, VisualRenderRequest, VisualStyle


def _chunk(name: bytes, payload: bytes) -> bytes:
    body = name + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def _png(width: int, height: int, rgba=(12, 14, 22, 255)) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = bytes(rgba) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


class ProviderMustNotRun:
    async def render(self, *args, **kwargs):
        raise AssertionError("external image provider must not run for deterministic visuals")


def _request(image: bytes, *, key="hybrid-visual-001", ratio=AspectRatio.PORTRAIT) -> VisualRenderRequest:
    return VisualRenderRequest(
        run_id="run-hybrid",
        idempotency_key=key,
        prompt="Server-owned technical editorial layout",
        aspect_ratio=ratio,
        style=VisualStyle.TECHNICAL_EDITORIAL,
        deterministic_png_base64=base64.b64encode(image).decode("ascii"),
        deterministic_png_sha256=hashlib.sha256(image).hexdigest(),
    )


@pytest.mark.asyncio
async def test_deterministic_png_is_persisted_without_external_provider_even_when_kill_switch_is_off(tmp_path):
    image = _png(108, 135)
    service = VisualRenderService(
        ProviderMustNotRun(),
        storage_dir=str(tmp_path),
        image_render_enabled=False,
    )

    result = await service.render_deterministic(_request(image))

    assert result.status == RenderStatus.READY
    assert result.provider == "DeterministicBrowserRenderer"
    assert result.width == 108
    assert result.height == 135
    assert result.asset_sha256 == hashlib.sha256(image).hexdigest()
    assert (tmp_path / result.asset_url.rsplit("/", 1)[-1]).read_bytes() == image


@pytest.mark.asyncio
async def test_deterministic_png_fails_closed_on_digest_mismatch(tmp_path):
    image = _png(108, 135)
    req = _request(image)
    req.deterministic_png_sha256 = "0" * 64
    service = VisualRenderService(ProviderMustNotRun(), storage_dir=str(tmp_path))

    result = await service.render_deterministic(req)

    assert result.status == RenderStatus.FAILED
    assert "digest" in result.error_message.lower()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_deterministic_png_rejects_non_png_bytes(tmp_path):
    payload = b"not an image"
    service = VisualRenderService(ProviderMustNotRun(), storage_dir=str(tmp_path))

    result = await service.render_deterministic(_request(payload))

    assert result.status == RenderStatus.FAILED
    assert "png" in result.error_message.lower()


@pytest.mark.asyncio
async def test_deterministic_png_rejects_wrong_aspect_ratio(tmp_path):
    square = _png(100, 100)
    service = VisualRenderService(ProviderMustNotRun(), storage_dir=str(tmp_path))

    result = await service.render_deterministic(_request(square, ratio=AspectRatio.PORTRAIT))

    assert result.status == RenderStatus.FAILED
    assert "aspect ratio" in result.error_message.lower()


@pytest.mark.asyncio
async def test_deterministic_idempotency_is_bound_to_exact_png_bytes(tmp_path):
    first = _png(108, 135, rgba=(12, 14, 22, 255))
    second = _png(108, 135, rgba=(13, 14, 22, 255))
    service = VisualRenderService(ProviderMustNotRun(), storage_dir=str(tmp_path))

    result_a = await service.render_deterministic(_request(first, key="hybrid-same-key"))
    result_b = await service.render_deterministic(_request(first, key="hybrid-same-key"))
    conflict = await service.render_deterministic(_request(second, key="hybrid-same-key"))

    assert result_a.status == RenderStatus.READY
    assert result_b.render_id == result_a.render_id
    assert conflict.status == RenderStatus.FAILED
    assert "idempotency key" in conflict.error_message.lower()
