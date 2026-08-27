from datetime import datetime, timezone

from db.mongo import get_db
from models.content_run import ContentRunStatus, StageStatus


_STAGE_NAMES = ("research", "write", "edit", "visual")
_REVIEWABLE_STATUSES = (
    ContentRunStatus.TEXT_READY.value,
    ContentRunStatus.READY_FOR_REVIEW.value,
)


def _now():
    return datetime.now(timezone.utc)


class ContentRunRepository:
    """Persistence boundary for authoritative generation runs."""

    @staticmethod
    def _collection():
        db = get_db()
        return None if db is None else db["content_runs"]

    async def create(self, context, idea: str) -> bool:
        collection = self._collection()
        if collection is None:
            return False

        now = _now()
        stages = {
            name: {
                "status": StageStatus.PENDING.value,
                "output": None,
                "selected_model": None,
                "provider": None,
                "attempt_failures": 0,
                "last_error": None,
                "started_at": None,
                "completed_at": None,
            }
            for name in _STAGE_NAMES
        }

        doc = {
            "run_id": context.run_id,
            "workspace_id": context.workspace_id,
            "topic": context.topic,
            "style": context.style,
            "idea": idea,
            "status": ContentRunStatus.GENERATING.value,
            "content_profile_id": context.content_profile_id,
            "content_profile_snapshot": context.content_profile_snapshot,
            "requested_target_language": context.requested_target_language.value,
            "resolved_target_language": context.resolved_target_language.value,
            "image_prompt_language": context.image_prompt_language.value,
            "stages": stages,
            "final_status": None,
            "final_content": None,
            "visual_prompt": None,
            "visual_render": None,
            "memory_check": None,
            "approval": None,
            "post_id": None,
            "failure_stage": None,
            "failure_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        await collection.update_one(
            {"run_id": context.run_id},
            {"$setOnInsert": doc},
            upsert=True,
        )
        return True

    async def mark_stage_started(self, run_id: str, stage: str, model: str | None, provider: str | None):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                f"stages.{stage}.status": StageStatus.RUNNING.value,
                f"stages.{stage}.selected_model": model,
                f"stages.{stage}.provider": provider,
                f"stages.{stage}.started_at": now,
                "updated_at": now,
            }},
        )

    async def mark_attempt_failed(self, run_id: str, stage: str, reason: str):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {
                "$inc": {f"stages.{stage}.attempt_failures": 1},
                "$set": {f"stages.{stage}.last_error": reason, "updated_at": now},
            },
        )

    async def mark_stage_completed(self, run_id: str, stage: str, output: str):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                f"stages.{stage}.status": StageStatus.COMPLETED.value,
                f"stages.{stage}.output": output,
                f"stages.{stage}.completed_at": now,
                "updated_at": now,
            }},
        )

    async def mark_stage_failed(self, run_id: str, stage: str, reason: str, terminal: bool = True):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        fields = {
            f"stages.{stage}.status": StageStatus.FAILED.value,
            f"stages.{stage}.last_error": reason,
            "updated_at": now,
        }
        if terminal:
            fields.update({
                "status": ContentRunStatus.FAILED.value,
                "failure_stage": stage,
                "failure_reason": reason,
            })
        await collection.update_one({"run_id": run_id}, {"$set": fields})

    async def mark_text_ready(self, run_id: str, final_content: str, final_status: str):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                "status": ContentRunStatus.TEXT_READY.value,
                "final_content": final_content,
                "final_status": final_status,
                "updated_at": now,
            }},
        )

    async def mark_ready_for_review(self, run_id: str, visual_prompt: str | None, post_id: str | None):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                "status": ContentRunStatus.READY_FOR_REVIEW.value,
                "visual_prompt": visual_prompt,
                "post_id": post_id,
                "updated_at": now,
            }},
        )

    async def record_visual_render(self, req, result) -> bool:
        collection = self._collection()
        if collection is None:
            return False

        now = _now()
        snapshot = {
            "render_id": result.render_id,
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "provider": result.provider,
            "asset_url": result.asset_url,
            "asset_sha256": result.asset_sha256,
            "width": result.width,
            "height": result.height,
            "prompt_used": result.prompt_used,
            "requested_prompt": req.prompt,
            "aspect_ratio": req.aspect_ratio.value if hasattr(req.aspect_ratio, "value") else str(req.aspect_ratio),
            "style": req.style.value if hasattr(req.style, "value") else str(req.style),
            "idempotency_key": req.idempotency_key,
            "error_message": result.error_message,
            "rendered_at": now,
        }
        update_result = await collection.update_one(
            {"run_id": req.run_id, "status": {"$in": list(_REVIEWABLE_STATUSES)}},
            {"$set": {"visual_prompt": req.prompt, "visual_render": snapshot, "updated_at": now}},
        )
        return bool(update_result.matched_count)

    async def mark_failed(self, run_id: str, stage: str, reason: str):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                "status": ContentRunStatus.FAILED.value,
                "failure_stage": stage,
                "failure_reason": reason,
                "updated_at": now,
            }},
        )
