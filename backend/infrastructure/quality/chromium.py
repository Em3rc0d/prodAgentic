from __future__ import annotations

import os

import httpx

from domain.quality.models import VisualQAObservationV1
from domain.rendering.models import RendererRequestV1


class VisualInspectorError(RuntimeError):
    pass


class ChromiumVisualQAAdapter:
    """Structural visual-QA adapter over the same isolated Chromium renderer."""

    version = "dom-geometry-v1"

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float | None = None):
        configured = (base_url or os.getenv("PRODAGENTIC_RENDERER_URL", "http://127.0.0.1:4100")).strip()
        if not configured.startswith(("http://", "https://")):
            raise ValueError("PRODAGENTIC_RENDERER_URL must use http or https")
        self.base_url = configured.rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("PRODAGENTIC_RENDERER_TIMEOUT_SECONDS", "30"))
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("visual inspector timeout must be between 1 and 120 seconds")

    async def inspect(self, request: RendererRequestV1) -> tuple[VisualQAObservationV1, ...]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/qa",
                    json=request.model_dump(mode="json"),
                    headers={"content-type": "application/json"},
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise VisualInspectorError("Chromium visual QA transport failed") from exc

        if response.status_code >= 500:
            raise VisualInspectorError("Chromium visual QA unavailable")
        if response.status_code != 200:
            raise VisualInspectorError("Chromium visual QA rejected the render contract")
        try:
            payload = response.json()
        except ValueError as exc:
            raise VisualInspectorError("Chromium visual QA returned invalid JSON") from exc

        if payload.get("render_id") != request.render_id:
            raise VisualInspectorError("visual QA render_id mismatch")
        if payload.get("render_input_digest") != request.render_input_digest:
            raise VisualInspectorError("visual QA render input digest mismatch")
        if payload.get("inspector_version") != self.version:
            raise VisualInspectorError("visual QA inspector version mismatch")

        rows = payload.get("observations")
        if not isinstance(rows, list) or len(rows) != len(request.pages):
            raise VisualInspectorError("visual QA observation count mismatch")
        try:
            observations = tuple(VisualQAObservationV1.model_validate(row) for row in rows)
        except Exception as exc:
            raise VisualInspectorError("visual QA observations violate VisualQAObservationV1") from exc
        if tuple(item.page_index for item in observations) != tuple(range(len(request.pages))):
            raise VisualInspectorError("visual QA page indices are not contiguous")
        return observations
