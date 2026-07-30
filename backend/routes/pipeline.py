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

class VisualRenderRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    style: str = ""

@router.post("/visual-renders")
async def render_visual(req: VisualRenderRequest):
    """Render an image from a prompt."""
    from agents.adapters.image import PollinationsImageAdapter
    adapter = PollinationsImageAdapter()
    try:
        result = await adapter.render(prompt=req.prompt, aspect_ratio=req.aspect_ratio, style=req.style)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
