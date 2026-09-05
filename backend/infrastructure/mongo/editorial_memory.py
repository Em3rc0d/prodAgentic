from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.planning.models import (
    EditorialMemoryEntry,
    LifecycleSource,
    canonicalize_topic,
    normalize_text,
    semantic_fingerprint,
)
from domain.tenants.models import TenantContext
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


_WEIGHT = {
    LifecycleSource.PUBLISHED: 1.0,
    LifecycleSource.PUBLISHING: 1.0,
    LifecycleSource.SCHEDULED: 1.0,
    LifecycleSource.APPROVED: 1.0,
    LifecycleSource.READY_FOR_REVIEW: 0.6,
}
_PRIORITY = {
    LifecycleSource.READY_FOR_REVIEW: 1,
    LifecycleSource.APPROVED: 2,
    LifecycleSource.SCHEDULED: 3,
    LifecycleSource.PUBLISHING: 4,
    LifecycleSource.PUBLISHED: 5,
}


def _dt(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return fallback
    return fallback


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _state(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


class MongoEditorialMemoryProjector:
    """Rebuildable S2 read-model projector.

    Native MK1 lifecycle evidence wins when available. During the migration
    window, still-authoritative MK0 ContentRuns are projected conservatively so
    approved/scheduled/published work is not forgotten before S7/S10 cutover.
    """

    def __init__(self, db: Any, context: TenantContext, repository: MongoPlanningRepository):
        self.context = context
        self.repository = repository
        self.items = TenantScopedMongoRepository(db, "content_items", context)
        self.approvals = TenantScopedMongoRepository(db, "approvals", context)
        self.schedules = TenantScopedMongoRepository(db, "schedules", context)
        self.publications = TenantScopedMongoRepository(db, "publications", context)
        self.legacy_runs = TenantScopedMongoRepository(db, "content_runs", context)

    async def refresh(self, profile_id: str, now: datetime) -> int:
        native = await self._native_entries(profile_id, now)
        legacy = await self._legacy_entries(profile_id, now)
        await self.repository.replace_projected_memory(profile_id, native, "native-")
        await self.repository.replace_projected_memory(profile_id, legacy, "mk0-")
        return len(native) + len(legacy)

    async def _native_entries(self, profile_id: str, now: datetime) -> list[EditorialMemoryEntry]:
        items = await self.items.find_many({"profile_id": profile_id})
        content_ids = [str(item.get("content_id")) for item in items if item.get("content_id")]
        if not content_ids:
            return []

        approvals = await self.approvals.find_many({"content_id": {"$in": content_ids}})
        approval_ids = [str(item.get("approval_id")) for item in approvals if item.get("approval_id")]
        schedules = await self.schedules.find_many({"approval_id": {"$in": approval_ids}}) if approval_ids else []
        publications = await self.publications.find_many({"approval_id": {"$in": approval_ids}}) if approval_ids else []

        approvals_by_content: dict[str, list[dict]] = {}
        for approval in approvals:
            approvals_by_content.setdefault(str(approval.get("content_id")), []).append(approval)
        schedules_by_approval: dict[str, list[dict]] = {}
        for schedule in schedules:
            schedules_by_approval.setdefault(str(schedule.get("approval_id")), []).append(schedule)
        publications_by_approval: dict[str, list[dict]] = {}
        for publication in publications:
            publications_by_approval.setdefault(str(publication.get("approval_id")), []).append(publication)

        entries: list[EditorialMemoryEntry] = []
        for item in items:
            content_id = str(item.get("content_id") or "").strip()
            if not content_id:
                continue
            source = None
            effective_at = _dt(item.get("updated_at"), now)
            revision_id = str(item.get("current_revision_id") or content_id)
            strongest_priority = 0

            for approval in approvals_by_content.get(content_id, []):
                approval_id = str(approval.get("approval_id") or "")
                candidate_source = LifecycleSource.APPROVED
                candidate_time = _dt(approval.get("approved_at"), effective_at)
                candidate_revision = str(approval.get("revision_id") or revision_id)

                for schedule in schedules_by_approval.get(approval_id, []):
                    if _state(schedule.get("state")) == LifecycleSource.SCHEDULED.value:
                        if _PRIORITY[LifecycleSource.SCHEDULED] > _PRIORITY[candidate_source]:
                            candidate_source = LifecycleSource.SCHEDULED
                            candidate_time = _dt(schedule.get("scheduled_for"), candidate_time)

                for publication in publications_by_approval.get(approval_id, []):
                    publication_state = _state(publication.get("state"))
                    if publication_state in {LifecycleSource.PUBLISHING.value, LifecycleSource.PUBLISHED.value}:
                        publication_source = LifecycleSource(publication_state)
                        if _PRIORITY[publication_source] > _PRIORITY[candidate_source]:
                            candidate_source = publication_source
                            candidate_time = _dt(
                                publication.get("completed_at") or publication.get("started_at"),
                                candidate_time,
                            )

                if _PRIORITY[candidate_source] > strongest_priority:
                    source = candidate_source
                    effective_at = candidate_time
                    revision_id = candidate_revision
                    strongest_priority = _PRIORITY[candidate_source]

            if source is None and _state(item.get("editorial_state")) == LifecycleSource.READY_FOR_REVIEW.value:
                source = LifecycleSource.READY_FOR_REVIEW
                strongest_priority = _PRIORITY[source]

            if source is None or strongest_priority == 0:
                continue

            canonical_topic = str(item.get("canonical_topic") or "").strip()
            if not canonical_topic:
                continue
            angle = str(item.get("angle") or "").strip() or "unspecified angle"
            hook = str(item.get("hook_pattern") or "").strip() or "unspecified"
            role = str(item.get("role") or "").strip() or "unspecified"
            fmt = str(item.get("format") or "text")
            visual = item.get("visual_pattern")
            subtopics = _strings(item.get("subtopics"))
            entries.append(
                EditorialMemoryEntry(
                    memory_id=f"native-{content_id}-{revision_id}",
                    tenant_id=self.context.tenant_id,
                    profile_id=profile_id,
                    content_id=content_id,
                    revision_id=revision_id,
                    lifecycle_source=source,
                    canonical_topic=canonicalize_topic(canonical_topic),
                    subtopics=subtopics,
                    angle=angle,
                    hook_pattern=hook,
                    role=role,
                    format=fmt,
                    visual_pattern=str(visual) if visual else None,
                    entities=(),
                    semantic_fingerprint=semantic_fingerprint(canonical_topic, *subtopics, angle),
                    effective_at=effective_at,
                    weight=_WEIGHT[source],
                    created_at=now,
                )
            )
        return entries

    async def _legacy_entries(self, profile_id: str, now: datetime) -> list[EditorialMemoryEntry]:
        eligible = [source.value for source in LifecycleSource]
        runs = await self.legacy_runs.find_many(
            {"content_profile_id": profile_id, "status": {"$in": eligible}},
            sort=[("updated_at", -1)],
        )
        entries: list[EditorialMemoryEntry] = []
        for run in runs:
            status = _state(run.get("status"))
            if status not in eligible:
                continue
            source = LifecycleSource(status)
            run_id = str(run.get("run_id") or "").strip()
            topic = str(run.get("topic") or "").strip()
            if not run_id or not topic:
                continue
            approval = run.get("approval") if isinstance(run.get("approval"), dict) else {}
            schedule = run.get("schedule") if isinstance(run.get("schedule"), dict) else {}
            publication = run.get("publication") if isinstance(run.get("publication"), dict) else {}
            revision_id = str(approval.get("approval_id") or run_id)
            effective_at = _dt(run.get("updated_at") or run.get("created_at"), now)
            if source == LifecycleSource.APPROVED:
                effective_at = _dt(approval.get("approved_at"), effective_at)
            elif source == LifecycleSource.SCHEDULED:
                effective_at = _dt(schedule.get("scheduled_for"), effective_at)
            elif source in (LifecycleSource.PUBLISHING, LifecycleSource.PUBLISHED):
                effective_at = _dt(publication.get("completed_at") or publication.get("started_at"), effective_at)

            idea = str(run.get("idea") or "").strip()
            style = str(run.get("style") or "").strip()
            angle = idea or style or "legacy concept"
            has_visual = bool(run.get("visual_render") or approval.get("visual_render"))
            entries.append(
                EditorialMemoryEntry(
                    memory_id=f"mk0-{run_id}-{status.lower()}",
                    tenant_id=self.context.tenant_id,
                    profile_id=profile_id,
                    content_id=run_id,
                    revision_id=revision_id,
                    lifecycle_source=source,
                    canonical_topic=canonicalize_topic(topic),
                    subtopics=(),
                    angle=angle,
                    hook_pattern=f"legacy:{normalize_text(style) or 'unknown'}",
                    role="legacy",
                    format="single_image" if has_visual else "text",
                    visual_pattern="legacy_visual" if has_visual else None,
                    entities=(),
                    semantic_fingerprint=semantic_fingerprint(topic, idea, style),
                    effective_at=effective_at,
                    weight=_WEIGHT[source],
                    created_at=now,
                )
            )
        return entries
