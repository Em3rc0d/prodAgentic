from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest

router = APIRouter(tags=["pipeline"])


from agents.idea_generator import GenerationIdeasFailed
from fastapi import HTTPException

@router.post("/ideas")
async def get_ideas(request: Request, req: IdeasRequest):
    """Generate 7 LinkedIn post ideas for a given topic and style."""
    pipeline = request.app.state.container.pipeline_service
    try:
        ideas = await pipeline.generate_ideas(req.topic, req.style)
        return {"ideas": ideas, "topic": req.topic, "style": req.style}
    except GenerationIdeasFailed:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "IDEA_GENERATION_FAILED",
                "message": "The model routing policy could not produce seven valid ideas."
            }
        )


@router.get("/pipeline/stream")
async def pipeline_stream(
    request: Request,
    idea: str = Query(..., description="The selected idea to expand"),
    topic: str = Query(..., description="Original topic"),
    style: str = Query("educational", description="Post style: educational | storytelling | controversial"),
):
    """
    SSE endpoint that streams the full Research → Write → Edit pipeline.
    Connect with EventSource on the frontend.
    """
    pipeline = request.app.state.container.pipeline_service
    
    async def event_generator():
        async for event in pipeline.run_pipeline_stream(idea, topic, style):
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
