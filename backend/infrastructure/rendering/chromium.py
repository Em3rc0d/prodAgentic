from __future__ import annotations

import base64
import logging
import os

import httpx

from domain.rendering.models import RendererRequestV1
from domain.rendering.ports import RenderedPageBytes, RendererPortError


_MAX_PAGE_BYTES = 16 * 1024 * 1024
_LOG = logging.getLogger(__name__)


class ChromiumRendererAdapter:
    """HTTP adapter for the isolated Playwright/Chromium renderer runtime."""

    name = "ChromiumRendererAdapter"
    version = "playwright-1.62.1-chromium-v1"

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float | None = None):
        configured = (base_url or os.getenv("PRODAGENTIC_RENDERER_URL", "http://127.0.0.1:4100")).strip()
        if not configured.startswith(("http://", "https://")):
            raise ValueError("PRODAGENTIC_RENDERER_URL must use http or https")
        self.base_url = configured.rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("PRODAGENTIC_RENDERER_TIMEOUT_SECONDS", "30"))
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("renderer timeout must be between 1 and 120 seconds")

    async def render(self, request: RendererRequestV1) -> tuple[RenderedPageBytes, ...]:
        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                # RendererPort is an internal service boundary. Ambient HTTP(S)_PROXY
                # configuration must not be allowed to hijack Docker/service-name
                # traffic or turn a healthy local renderer into an external 502.
                async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                    response = await client.post(
                        f"{self.base_url}/render",
                        json=request.model_dump(mode="json"),
                        headers={"content-type": "application/json"},
                    )
                if response.status_code >= 500:
                    _LOG.warning(
                        "Chromium renderer server failure status=%s attempt=%s render_id=%s",
                        response.status_code,
                        attempt,
                        request.render_id,
                    )
                    raise RendererPortError("Chromium renderer unavailable", retryable=True)
                if response.status_code != 200:
                    _LOG.error(
                        "Chromium renderer contract rejection status=%s render_id=%s detail=%s",
                        response.status_code,
                        request.render_id,
                        _safe_renderer_detail(response),
                    )
                    raise RendererPortError("Chromium renderer rejected the render contract", retryable=False)
                payload = response.json()
                return self._decode_response(request, payload)
            except RendererPortError as exc:
                last_error = exc
                _LOG.warning(
                    "Chromium renderer port error retryable=%s attempt=%s render_id=%s reason=%s",
                    exc.retryable,
                    attempt,
                    request.render_id,
                    str(exc),
                )
                if not exc.retryable or attempt == 2:
                    raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                _LOG.warning(
                    "Chromium renderer transport error attempt=%s render_id=%s type=%s",
                    attempt,
                    request.render_id,
                    type(exc).__name__,
                )
                if attempt == 2:
                    raise RendererPortError("Chromium renderer transport failed", retryable=True) from exc
            except (ValueError, TypeError, KeyError) as exc:
                _LOG.error(
                    "Chromium renderer invalid response render_id=%s type=%s",
                    request.render_id,
                    type(exc).__name__,
                )
                raise RendererPortError("Chromium renderer returned an invalid response", retryable=False) from exc
        raise RendererPortError("Chromium renderer failed", retryable=True) from last_error

    def _decode_response(self, request: RendererRequestV1, payload: dict) -> tuple[RenderedPageBytes, ...]:
        if payload.get("render_id") != request.render_id:
            raise RendererPortError("renderer response render_id mismatch")
        if payload.get("render_input_digest") != request.render_input_digest:
            raise RendererPortError("renderer response input digest mismatch")
        if payload.get("renderer_name") != self.name or payload.get("renderer_version") != self.version:
            raise RendererPortError("renderer identity/version mismatch")
        pages = payload.get("pages")
        if not isinstance(pages, list) or len(pages) != len(request.pages):
            raise RendererPortError("renderer response page count mismatch")

        decoded: list[RenderedPageBytes] = []
        for expected, item in zip(request.pages, pages, strict=True):
            if not isinstance(item, dict):
                raise RendererPortError("renderer page payload is invalid")
            if item.get("page_id") != expected.page_id or item.get("page_index") != expected.page_index:
                raise RendererPortError("renderer page identity mismatch")
            if item.get("width") != request.canvas_width or item.get("height") != request.canvas_height:
                raise RendererPortError("renderer page dimensions mismatch")
            if item.get("content_type") != "image/png":
                raise RendererPortError("renderer returned unsupported content type")
            encoded = item.get("data_base64")
            if not isinstance(encoded, str):
                raise RendererPortError("renderer page bytes are missing")
            try:
                data = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise RendererPortError("renderer page bytes are not valid base64") from exc
            if not data or len(data) > _MAX_PAGE_BYTES:
                raise RendererPortError("renderer page byte size is outside certified limits")
            decoded.append(
                RenderedPageBytes(
                    page_id=expected.page_id,
                    page_index=expected.page_index,
                    width=request.canvas_width,
                    height=request.canvas_height,
                    content_type="image/png",
                    data=data,
                )
            )
        return tuple(decoded)


def _safe_renderer_detail(response: httpx.Response) -> str:
    """Return bounded renderer-owned diagnostic text without user payloads."""
    try:
        payload = response.json()
    except ValueError:
        return "non-json renderer response"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, str):
        return "renderer response omitted detail"
    return detail[:240]
