import logging

from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest
from agents.idea_generator import GenerationIdeasFailed

from core.context import TargetLanguageCode, ImagePromptLanguageCode
from db.content_runs import ContentRunRepository
from db.mongo import get_db


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
    idea: str = Query(..., description="The selected idea to expand"),
    topic: str = Query(..., description="Original topic"),
    style: str = Query("educational", description="Post style"),
    target_language: TargetLanguageCode = Query(TargetLanguageCode.ES),
    image_prompt_language: ImagePromptLanguageCode = Query(ImagePromptLanguageCode.EN),
    content_profile_id: str | None = Query(None),
    pipeline=Depends(get_ready_pipeline_service),
):
    profile_id, profile_snapshot = await _resolve_content_profile(content_profile_id)

    async def event_generator():
        if profile_snapshot is None:
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
                profile_id,
                profile_snapshot,
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


from models.visual import VisualRenderRequest


@router.post("/visual-renders")
async def render_visual(req: VisualRenderRequest, request: Request):
    visual_service = request.app.state.container.visual_service
    run_repository = ContentRunRepository()
    try:
        result = await visual_service.render(req)
        try:
            await run_repository.record_visual_render(req, result)
        except Exception as persistence_error:
            logger.warning(
                "Visual render completed but ContentRun attachment failed for run_id=%s: %s",
                req.run_id,
                persistence_error,
            )
        return result.model_dump()
    except Exception:
        from models.visual import VisualRenderResponse, RenderStatus
        import uuid

        err_res = VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider="Unknown",
            prompt_used=req.prompt,
            error_message="Internal Server Error",
        )
        try:
            await run_repository.record_visual_render(req, err_res)
        except Exception as persistence_error:
            logger.warning(
                "Visual failure snapshot could not be attached for run_id=%s: %s",
                req.run_id,
                persistence_error,
            )
        return err_res.model_dump()
