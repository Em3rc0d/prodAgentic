from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core.visual_direction import VisualDirectionPolicy, VisualRenderer
from models.visual import VisualRenderRequest
from routes.pipeline import render_visual
from routes.visual_plans import get_visual_render_plan


class FakeCollection:
    def __init__(self, document):
        self.document = document
        self.last_query = None

    async def find_one(self, query, projection=None):
        self.last_query = query
        return self.document


class FakeDb:
    def __init__(self, document):
        self.collection = FakeCollection(document)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def _request(visual_service=None):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                container=SimpleNamespace(
                    settings=SimpleNamespace(app_workspace_id="workspace-a"),
                    visual_service=visual_service,
                )
            )
        )
    )


@pytest.mark.asyncio
async def test_visual_plan_is_workspace_scoped_and_exposes_only_final_content(monkeypatch):
    db = FakeDb({
        "final_content": "Una arquitectura separa generación, validación y publicación en un pipeline explícito.",
        "style": "educational",
    })
    monkeypatch.setattr("routes.visual_plans.get_db", lambda: db)

    plan = await get_visual_render_plan("run-1", _request())

    assert db.collection.last_query == {"run_id": "run-1", "workspace_id": "workspace-a"}
    assert plan.run_id == "run-1"
    assert plan.policy_version == VisualDirectionPolicy.VERSION
    assert plan.renderer == VisualRenderer.DETERMINISTIC.value
    assert plan.final_content.startswith("Una arquitectura")
    assert plan.recommended_aspect_ratio.value == "4:5"
    assert not hasattr(plan, "source_packet")


@pytest.mark.asyncio
async def test_visual_plan_unknown_or_cross_workspace_run_is_404(monkeypatch):
    monkeypatch.setattr("routes.visual_plans.get_db", lambda: FakeDb(None))

    with pytest.raises(HTTPException) as exc:
        await get_visual_render_plan("run-secret", _request())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_server_selected_deterministic_direction_never_calls_generative_provider(monkeypatch):
    calls = []

    class FakeVisualService:
        async def render_deterministic(self, req):
            calls.append("deterministic")
            return SimpleNamespace(
                render_id="render-det",
                status=SimpleNamespace(value="FAILED"),
                provider="DeterministicBrowserRenderer",
                asset_url=None,
                asset_sha256=None,
                width=None,
                height=None,
                prompt_used=req.prompt,
                error_message="missing png in unit boundary",
                model_dump=lambda: {
                    "render_id": "render-det",
                    "status": "FAILED",
                    "provider": "DeterministicBrowserRenderer",
                    "prompt_used": req.prompt,
                    "error_message": "missing png in unit boundary",
                },
            )

        async def render(self, req):
            raise AssertionError("generative provider must not run")

    direction = VisualDirectionPolicy.select(
        "Una arquitectura de grounding valida un pipeline antes de publicar.",
        style="educational",
    )
    assert direction.renderer == VisualRenderer.DETERMINISTIC

    async def return_same(req, request):
        return req

    async def return_direction(req, request):
        return direction

    async def ignore_attachment(self, req, result):
        return True

    monkeypatch.setattr("routes.pipeline._resolve_visual_render_request", return_same)
    monkeypatch.setattr("routes.pipeline._load_visual_direction", return_direction)
    monkeypatch.setattr("routes.pipeline.ContentRunRepository.record_visual_render", ignore_attachment)

    result = await render_visual(
        VisualRenderRequest(
            run_id="run-1",
            idempotency_key="hybrid-route-123",
            prompt="technical editorial",
        ),
        _request(FakeVisualService()),
    )

    assert calls == ["deterministic"]
    assert result["provider"] == "DeterministicBrowserRenderer"


@pytest.mark.asyncio
async def test_deterministic_payload_cannot_force_generative_run(monkeypatch):
    class FakeVisualService:
        async def render(self, req):
            raise AssertionError("request must be rejected before provider call")

    direction = VisualDirectionPolicy.select(
        "Una decisión incómoda cambió nuestra forma de pensar sobre creatividad.",
        style="storytelling",
    )
    assert direction.renderer == VisualRenderer.GENERATIVE

    async def return_same(req, request):
        return req

    async def return_direction(req, request):
        return direction

    monkeypatch.setattr("routes.pipeline._resolve_visual_render_request", return_same)
    monkeypatch.setattr("routes.pipeline._load_visual_direction", return_direction)

    req = VisualRenderRequest(
        run_id="run-story",
        idempotency_key="hybrid-force-123",
        prompt="editorial illustration",
        deterministic_png_base64="aGVsbG8=",
        deterministic_png_sha256="0" * 64,
    )

    with pytest.raises(HTTPException) as exc:
        await render_visual(req, _request(FakeVisualService()))

    assert exc.value.status_code == 409
