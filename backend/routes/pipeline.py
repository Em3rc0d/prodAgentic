from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest
from agents.idea_generator import GenerationIdeasFailed
from pydantic import BaseModel

from core.context import LanguageCode

def get_ready_pipeline_service(request: Request):
    pipeline = request.app.state.container.pipeline_service
    if not request.app.state.container.router._get_adapters():
        raise HTTPException(status_code=503, detail="No viable provider adapters available.")
    return pipeline

router = APIRouter(tags=["pipeline"])

@router.post("/ideas")
async def get_ideas(req: IdeasRequest, pipeline = Depends(get_ready_pipeline_service)):
    """Generate 7 LinkedIn post ideas for a given topic and style."""
    try:
        ideas = await pipeline.generate_ideas(req.topic, req.style, req.target_language.value)
        return {"ideas": ideas, "topic": req.topic, "style": req.style}
    except GenerationIdeasFailed as e:
        print(f"[ERROR] GenerationIdeasFailed in /api/ideas: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "IDEA_GENERATION_FAILED",
                "message": "The model routing policy could not produce seven valid ideas."
            }
        )


@router.get("/pipeline/stream")
async def pipeline_stream(
    idea: str = Query(..., description="The selected idea to expand"),
    topic: str = Query(..., description="Original topic"),
    style: str = Query("educational", description="Post style: educational | storytelling | controversial"),
    target_language: LanguageCode = Query(LanguageCode.ES, description="Target language for the post"),
    image_prompt_language: LanguageCode = Query(LanguageCode.EN, description="Target language for the image prompt"),
    pipeline = Depends(get_ready_pipeline_service)
):
    """
    SSE endpoint that streams the full Research → Write → Edit pipeline.
    Connect with EventSource on the frontend.
    """
    
    async def event_generator():
        async for event in pipeline.run_pipeline_stream(idea, topic, style, target_language, image_prompt_language):
            data = event.get("data", "{}")
            yield f"data: {data}\n\n"
        # Signal stream end
        yield 'data: {"stage": "end"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )

from models.visual import VisualRenderRequest

@router.post("/visual-renders")
async def render_visual(req: VisualRenderRequest, request: Request):
    """Render an image from a prompt."""
    visual_service = request.app.state.container.visual_service
    try:
        result = await visual_service.render(req)
        return result.model_dump()
    except Exception as e:
        # Fallback for unexpected failures outside service bounds
        from models.visual import VisualRenderResponse, RenderStatus
        import uuid
        err_res = VisualRenderResponse(
            render_id=str(uuid.uuid4()),
            status=RenderStatus.FAILED,
            provider="Unknown",
            prompt_used=req.prompt,
            error_message="Internal Server Error"
        )
        return err_res.model_dump()
