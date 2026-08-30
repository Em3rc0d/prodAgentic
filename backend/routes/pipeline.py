import logging

from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest
from agents.idea_generator import GenerationIdeasFailed

from core.context import TargetLanguageCode, ImagePromptLanguageCode
from core.visual_direction import VisualDirection, VisualDirectionPolicy, VisualRenderer
from db.content_runs import ContentRunRepository
from db.mongo import get_db
from db.source_packets import SourcePacketRepository
from models.visual import AspectRatio, VisualRenderRequest, VisualStyle


logger = logging.getLogger(__name__)


def get_ready_pipeline_service(request: Request):
    pipeline = request.app.state.container.pipeline_service
    if not request.app.state.container.router._get_adapters():
        raise HTTPException(status_code=503, detail="No viable provider adapters available.")
    return pipeline


async def _resolve_content_profile(profile_id: str | None):
    db = get_db()
    if db is None:
        if profile_id:
            raise HTTPException(status_code=503, detail="MongoDB required for explicit content profile")
        return None, None

    collection = db["content_profiles"]
    if profile_id:
        doc = await collection.find_one({"profile_id": profile_id, "archived": {"$ne": True}})
        if doc is None:
            raise HTTPException(status_code=404, detail="Active content profile not found")
    else:
        doc = await collection.find_one({"is_default": True, "archived": {"$ne": True}})

    if doc is None:
        return None, None

    snapshot = {key: value for key, value in doc.items() if key != "_id"}
    return doc["profile_id"], snapshot


def _authoritative_workspace_id(request: Request) -> str:
    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    workspace_id = getattr(settings, "app_workspace_id", None)
    if not isinstance(workspace_id, str) or not workspace_id:
        raise HTTPException(status_code=503, detail="Authoritative workspace configuration is unavailable")
    return workspace_id


async def _load_visual_direction(
    req: VisualRenderRequest,
    request: Request,
) -> VisualDirection | None:
    db = get_db()
    if db is None:
        return None

    run_doc = await db["content_runs"].find_one(
        {
            "run_id": req.run_id,
            "workspace_id": _authoritative_workspace_id(request),
        },
        {"final_content": 1, "style": 1},
    )
    if not run_doc or not isinstance(run_doc.get("final_content"), str) or not run_doc["final_content"].strip():
        return None
    return VisualDirectionPolicy.select(
        run_doc["final_content"],
        style=run_doc.get("style") or "educational",
    )


async def _resolve_visual_render_request(
    req: VisualRenderRequest,
    request: Request,
) -> VisualRenderRequest:
    """Translate only the exact legacy Studio 16:9 + Default pair.

    Intentional manual aspect/style choices remain untouched. Renderer choice is
    a separate server authority resolved by ``_load_visual_direction``.
    """
    if not (req.aspect_ratio == AspectRatio.WIDESCREEN and req.style == VisualStyle.DEFAULT):
        return req

    direction = await _load_visual_direction(req, request)
    if direction is None:
        return req
    return req.model_copy(
        update={
            "aspect_ratio": AspectRatio(direction.recommended_aspect_ratio),
            "style": VisualStyle(direction.recommended_style),
        }
    )


router = APIRouter(tags=["pipeline"])


@router.post("/ideas")
async def get_ideas(req: IdeasRequest, pipeline=Depends(get_ready_pipeline_service)):
    try:
        profile_id, profile_snapshot = await _resolve_content_profile(req.content_profile_id)
        if profile_snapshot is None:
            ideas = await pipeline.generate_ideas(req.topic, req.style, req.target_language.value)
        else:
            ideas = await pipeline.generate_ideas(
                req.topic,
                req.style,
                req.target_language.value,
                profile_id,
                profile_snapshot,
            )
        return {
            "ideas": ideas,
            "topic": req.topic,
            "style": req.style,
            "content_profile_id": profile_id,
        }
    except GenerationIdeasFailed as e:
        print(f"[ERROR] GenerationIdeasFailed in /api/ideas: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "IDEA_GENERATION_FAILED",
                "message": "The model routing policy could not produce seven valid ideas.",
            },
        )


@router.get("/pipeline/stream")
async def pipeline_stream(
    request: Request,
    idea: str = Query(..., description="The selected idea to expand"),
    topic: str = Query(..., description="Original topic"),
    style: str = Query("educational", description="Post style"),
    target_language: TargetLanguageCode = Query(TargetLanguageCode.ES),
    image_prompt_language: ImagePromptLanguageCode = Query(ImagePromptLanguageCode.EN),
    content_profile_id: str | None = Query(None),
    source_packet_id: str | None = Query(
        None,
        description="Opaque id of an immutable server-scoped SourcePacket to constrain generation",
    ),
    pipeline=Depends(get_ready_pipeline_service),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for durable content generation")

    source_packet = None
    if source_packet_id:
        source_packet = await SourcePacketRepository(db).get(
            _authoritative_workspace_id(request),
            source_packet_id,
        )
        if source_packet is None:
            raise HTTPException(status_code=404, detail="Source packet not found")

    profile_id, profile_snapshot = await _resolve_content_profile(content_profile_id)

    async def event_generator():
        if profile_snapshot is None:
            if source_packet is None:
                stream = pipeline.run_pipeline_stream(
                    idea,
                    topic,
                    style,
                    target_language,
                    image_prompt_language,
                )
            else:
                stream = pipeline.run_pipeline_stream(
                    idea,
                    topic,
                    style,
                    target_language,
                    image_prompt_language,
                    source_packet=source_packet,
                )
        else:
            if source_packet is None:
                stream = pipeline.run_pipeline_stream(
                    idea,
                    topic,
                    style,
                    target_language,
                    image_prompt_language,
                    profile_id,
                    profile_snapshot,
                )
            else:
                stream = pipeline.run_pipeline_stream(
                    idea,
                    topic,
                    style,
                    target_language,
                    image_prompt_language,
                    profile_id,
                    profile_snapshot,
                    source_packet=source_packet,
                )

        async for event in stream:
            data = event.get("data", "{}")
            yield f"data: {data}\n\n"
        yield 'data: {"stage": "end"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/visual-renders")
async def render_visual(req: VisualRenderRequest, request: Request):
    visual_service = request.app.state.container.visual_service
    run_repository = ContentRunRepository()
    effective_req = await _resolve_visual_render_request(req, request)
    direction = await _load_visual_direction(effective_req, request)
    try:
        if direction is not None and direction.renderer == VisualRenderer.DETERMINISTIC:
            result = await visual_service.render_deterministic(effective_req)
        else:
            if effective_req.deterministic_png_base64 or effective_req.deterministic_png_sha256:
                raise HTTPException(
                    status_code=409,
                    detail="Deterministic PNG supplied for a run whose server-owned renderer is not deterministic",
                )
            result = await visual_service.render(effective_req)

        try:
            await run_repository.record_visual_render(effective_req, result)
        except Exception as persistence_error:
            logger.warning(
                "Visual render completed but ContentRun attachment failed for run_id=%s: %s",
                effective_req.run_id,
                persistence_error,
            )
        return result.model_dump()
    except HTTPException:
        raise
    except Exception:
        from models.visual import VisualRenderResponse, RenderStatus
        import uuid

        err_res = VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider="Unknown",
            prompt_used=effective_req.prompt,
            error_message="Internal Server Error",
        )
        try:
            await run_repository.record_visual_render(effective_req, err_res)
        except Exception as persistence_error:
            logger.warning(
                "Visual failure snapshot could not be attached for run_id=%s: %s",
                effective_req.run_id,
                persistence_error,
            )
        return err_res.model_dump()
