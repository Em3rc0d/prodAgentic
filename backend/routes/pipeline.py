from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from models.post import IdeasRequest
from agents.orchestrator import generate_ideas, run_pipeline_stream

router = APIRouter(tags=["pipeline"])


@router.post("/ideas")
async def get_ideas(req: IdeasRequest):
    """Generate 7 LinkedIn post ideas for a given topic and style."""
    ideas = await generate_ideas(req.topic, req.style)
    return {"ideas": ideas, "topic": req.topic, "style": req.style}


@router.get("/pipeline/stream")
async def pipeline_stream(
    idea: str = Query(..., description="The selected idea to expand"),
    topic: str = Query(..., description="Original topic"),
    style: str = Query("educational", description="Post style: educational | storytelling | controversial"),
):
    """
    SSE endpoint that streams the full Research → Write → Edit pipeline.
    Connect with EventSource on the frontend.
    """
    async def event_generator():
        async for event in run_pipeline_stream(idea, topic, style):
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
