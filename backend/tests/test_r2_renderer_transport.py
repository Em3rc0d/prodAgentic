import pytest

from domain.rendering.models import (
    RenderSafeZoneV1,
    RendererRequestV1,
    RendererThemeV1,
    ResolvedRenderBlockV1,
    ResolvedRenderPageV1,
)
from domain.rendering.ports import RendererPortError
from infrastructure.rendering import chromium as chromium_module
from infrastructure.rendering.chromium import ChromiumRendererAdapter


class _Response:
    status_code = 503

    def json(self):
        return {"detail": "synthetic renderer outage"}


class _Client:
    def __init__(self, calls, **kwargs):
        calls.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return _Response()


def _request() -> RendererRequestV1:
    digest = "a" * 64
    return RendererRequestV1(
        render_id=f"render-{digest}",
        revision_id="revision-r2",
        visual_spec_id="visual-r2",
        visual_spec_digest=digest,
        content_spec_digest=digest,
        design_profile_digest=digest,
        visual_pattern="carousel.educational",
        format="carousel",
        canvas_width=1080,
        canvas_height=1350,
        safe_zone=RenderSafeZoneV1(top=64, right=64, bottom=64, left=64),
        theme=RendererThemeV1(
            background="surface.canvas",
            surface="surface.paper",
            text="text.ink",
            muted_text="text.muted",
            accent="accent.signal",
            border="border.hairline",
            density="balanced",
            spacing_scale="standard",
            radius_scale="standard",
            icon_language="outline",
        ),
        pages=(
            ResolvedRenderPageV1(
                page_id="page-0",
                page_index=0,
                role="hook",
                layout_family="hero_stack",
                blocks=(
                    ResolvedRenderBlockV1(
                        block_id="headline",
                        kind="text",
                        role="headline",
                        text="Renderer transport regression",
                        editorial_critical=True,
                    ),
                ),
            ),
        ),
        render_input_digest=digest,
    )


@pytest.mark.asyncio
async def test_internal_renderer_transport_ignores_ambient_proxy_configuration(monkeypatch):
    calls = []

    def client_factory(**kwargs):
        return _Client(calls, **kwargs)

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setattr(chromium_module.httpx, "AsyncClient", client_factory)

    adapter = ChromiumRendererAdapter(base_url="http://renderer:4100", timeout_seconds=3)
    with pytest.raises(RendererPortError, match="unavailable") as exc_info:
        await adapter.render(_request())

    assert exc_info.value.retryable is True
    assert len(calls) == 2
    assert all(call["trust_env"] is False for call in calls)
