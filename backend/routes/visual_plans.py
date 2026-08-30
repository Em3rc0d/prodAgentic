from fastapi import APIRouter, HTTPException, Request

from core.visual_direction import VisualDirectionPolicy
from db.mongo import get_db
from models.visual import AspectRatio, VisualRenderPlan, VisualStyle


router = APIRouter(tags=["pipeline"])


def _workspace_id(request: Request) -> str:
    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    workspace_id = getattr(settings, "app_workspace_id", None)
    if not isinstance(workspace_id, str) or not workspace_id:
        raise HTTPException(status_code=503, detail="Authoritative workspace configuration is unavailable")
    return workspace_id


@router.get("/visual-renders/{run_id}/plan", response_model=VisualRenderPlan)
async def get_visual_render_plan(run_id: str, request: Request) -> VisualRenderPlan:
    """Return the server-owned renderer/format plan for one ContentRun.

    Only the already-authored final content is returned; evidence packets and
    hidden prompts remain outside this surface. Unknown and cross-workspace run
    identifiers are intentionally indistinguishable.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB required for visual render planning")

    doc = await db["content_runs"].find_one(
        {
            "run_id": run_id,
            "workspace_id": _workspace_id(request),
        },
        {"final_content": 1, "style": 1},
    )
    final_content = doc.get("final_content") if doc else None
    if not isinstance(final_content, str) or not final_content.strip():
        raise HTTPException(status_code=404, detail="Content run not found")

    direction = VisualDirectionPolicy.select(
        final_content,
        style=doc.get("style") or "educational",
    )
    return VisualRenderPlan(
        run_id=run_id,
        policy_version=VisualDirectionPolicy.VERSION,
        visual_format=direction.visual_format.value,
        renderer=direction.renderer.value,
        final_content=final_content,
        recommended_aspect_ratio=AspectRatio(direction.recommended_aspect_ratio),
        recommended_style=VisualStyle(direction.recommended_style),
    )
