import asyncio
import logging
import os
from datetime import datetime, timezone

from core.publication import (
    PublicationConflict,
    PublicationCoordinator,
    PublicationFailed,
    PublicationReconciliationRequired,
    PublicationUnavailable,
)
from db.mongo import get_db
from models.content_run import ContentRunStatus


logger = logging.getLogger(__name__)


def scheduler_enabled() -> bool:
    return os.environ.get("SCHEDULER_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def scheduler_poll_seconds() -> float:
    raw = os.environ.get("SCHEDULER_POLL_SECONDS", "30")
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 30.0


async def run_due_schedules_once(db=None, coordinator_factory=PublicationCoordinator, limit: int = 20) -> int:
    db = db or get_db()
    if db is None:
        return 0

    now = datetime.now(timezone.utc)
    cursor = (
        db["content_runs"]
        .find({
            "status": ContentRunStatus.SCHEDULED.value,
            "schedule.status": "SCHEDULED",
            "schedule.scheduled_for": {"$lte": now},
        })
        .sort("schedule.scheduled_for", 1)
        .limit(limit)
    )

    attempted = 0
    coordinator = coordinator_factory(db)
    async for doc in cursor:
        attempted += 1
        try:
            await coordinator.publish_run(doc["run_id"], expected_status=ContentRunStatus.SCHEDULED)
        except PublicationConflict:
            # Another worker/cancellation may have won the atomic claim.
            continue
        except PublicationUnavailable as exc:
            logger.error("Scheduled publication unavailable for run_id=%s: %s", doc.get("run_id"), exc)
        except PublicationFailed as exc:
            logger.error("Scheduled publication failed for run_id=%s: %s", doc.get("run_id"), exc)
        except PublicationReconciliationRequired as exc:
            logger.critical("Scheduled publication requires reconciliation for run_id=%s: %s", doc.get("run_id"), exc)
        except Exception:
            logger.exception("Unexpected scheduled publication error for run_id=%s", doc.get("run_id"))
    return attempted


async def scheduler_loop():
    if not scheduler_enabled():
        logger.info("Scheduler disabled by SCHEDULER_ENABLED")
        return

    logger.info("Scheduler started with %.1fs polling", scheduler_poll_seconds())
    while True:
        try:
            await run_due_schedules_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler iteration failed")
        await asyncio.sleep(scheduler_poll_seconds())
