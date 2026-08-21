from datetime import datetime, timezone

from db.mongo import get_db
from models.content_run import ContentRunStatus, StageStatus


_STAGE_NAMES = ("research", "write", "edit", "visual")


def _now():
    return datetime.now(timezone.utc)


class ContentRunRepository:
    """Persistence boundary for authoritative generation runs.

    All methods degrade to a no-op when MongoDB is unavailable so the existing
    generation pipeline can continue operating without persistence.
    """

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
            "topic": context.topic,
            "style": context.style,
            "idea": idea,
            "status": ContentRunStatus.GENERATING.value,
            "requested_target_language": context.requested_target_language.value,
            "resolved_target_language": context.resolved_target_language.value,
            "image_prompt_language": context.image_prompt_language.value,
            "stages": stages,
            "final_status": None,
            "final_content": None,
            "visual_prompt": None,
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
                "$set": {
                    f"stages.{stage}.last_error": reason,
                    "updated_at": now,
                },
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

    async def mark_stage_failed(self, run_id: str, stage: str, reason: str):
        collection = self._collection()
        if collection is None:
            return
        now = _now()
        await collection.update_one(
            {"run_id": run_id},
            {"$set": {
                f"stages.{stage}.status": StageStatus.FAILED.value,
                f"stages.{stage}.last_error": reason,
                "status": ContentRunStatus.FAILED.value,
                "failure_stage": stage,
                "failure_reason": reason,
                "updated_at": now,
            }},
        )

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
