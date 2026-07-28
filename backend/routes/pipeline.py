from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest
from agents.idea_generator import GenerationIdeasFailed

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
        ideas = await pipeline.generate_ideas(req.topic, req.style, req.target_language)
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
    target_language: str = Query("es", description="Target language for the post"),
    image_prompt_language: str = Query("en", description="Target language for the image prompt"),
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
