from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from domain.jobs.models import JobIntent
from domain.publishing.models import (
    PlatformCapabilityV1,
    PublicationState,
    PublicationV1,
    ScheduleState,
    ScheduleV1,
    deterministic_publication_id,
    deterministic_schedule_id,
    publication_operation_key,
)
from domain.production.models import ContentSpecV1, canonical_sha256 as production_sha256
from infrastructure.linkedin.adapter import (
    PreparedPublication,
    PlatformSafeFailure,
    PlatformUncertainFailure,
)


class PublishingAuthorityError(RuntimeError):
    pass


class PublishingUnavailable(PublishingAuthorityError):
    pass


class PublishingConflict(PublishingAuthorityError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _caption(content: ContentSpecV1) -> str:
    sections = [content.hook, content.body]
    if content.cta:
        sections.append(content.cta)
    if content.hashtags:
        sections.append(" ".join(content.hashtags))
    return "\n\n".join(section.strip() for section in sections if section and section.strip()).strip()


@dataclass(frozen=True)
class ScheduleResult:
    schedule: ScheduleV1
    capability: PlatformCapabilityV1


class SchedulingService:
    def __init__(self, *, approvals, schedules, connections, adapter):
        self.approvals = approvals
        self.schedules = schedules
        self.connections = connections
        self.adapter = adapter

    async def schedule_linkedin(
        self,
        *,
        tenant_id: str,
        approval_id: str,
        scheduled_for: datetime,
        timezone_context: str,
        destination: str = "member_feed",
    ) -> ScheduleResult:
        now = utc_now()
        if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
            raise PublishingConflict("scheduled_for must be timezone-aware")
        scheduled_for = scheduled_for.astimezone(timezone.utc)
        if scheduled_for <= now:
            raise PublishingConflict("scheduled_for must be in the future")

        approval = await self.approvals.get_bundle(tenant_id, approval_id)
        if approval is None or approval.tenant_id != tenant_id:
            raise PublishingAuthorityError("ApprovalBundleV2 not found")

        connection = await self.connections.get_linkedin()
        if connection is None:
            raise PublishingUnavailable("LinkedIn is not connected; use Manual Export or connect LinkedIn")
        capability = await self.adapter.capabilities(connection)
        if not capability.can_publish:
            raise PublishingUnavailable(capability.reason or "LinkedIn automatic publication unavailable")
        external_identity = capability.external_identity or ""
        requested_destination = destination.strip() or "member_feed"
        canonical_destination = f"{requested_destination}|{external_identity}"
        operation_key = publication_operation_key(
            tenant_id=tenant_id,
            approval_id=approval.approval_id,
            bundle_sha256=approval.bundle_sha256,
            provider="linkedin",
            external_identity=external_identity,
            destination=canonical_destination,
        )
        schedule_id = deterministic_schedule_id(
            tenant_id=tenant_id,
            approval_id=approval.approval_id,
            connection_id=connection["connection_id"],
            provider="linkedin",
            destination=canonical_destination,
            scheduled_for=scheduled_for,
            bundle_sha256=approval.bundle_sha256,
        )
        schedule = ScheduleV1(
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            approval_id=approval.approval_id,
            connection_id=connection["connection_id"],
            provider="linkedin",
            destination=canonical_destination,
            scheduled_for=scheduled_for,
            timezone_context=timezone_context.strip() or "UTC",
            state=ScheduleState.SCHEDULED,
            job_key=operation_key,
            bundle_sha256=approval.bundle_sha256,
            created_at=now,
        )
        return ScheduleResult(schedule=await self.schedules.create(schedule), capability=capability)


class PreparedPublicationBuilder:
    """Reopens exact immutable authority and rehashes AssetStore bytes immediately before upload."""

    def __init__(self, *, approvals, production, rendering, asset_store):
        self.approvals = approvals
        self.production = production
        self.rendering = rendering
        self.asset_store = asset_store

    async def build(self, *, tenant_id: str, publication: PublicationV1) -> PreparedPublication:
        approval = await self.approvals.get_bundle(tenant_id, publication.approval_id)
        if approval is None or approval.bundle_sha256 != publication.bundle_sha256:
            raise PlatformSafeFailure("Publication Approval authority mismatch")

        revision = await self.production.get_revision(tenant_id, approval.revision_id)
        if (
            revision is None
            or revision.content_id != approval.content_id
            or revision.revision_id != approval.revision_id
            or revision.content_spec_digest != approval.content_digest
            or revision.visual_spec_digest != approval.visual_spec_digest
        ):
            raise PlatformSafeFailure("Approved ContentRevision authority mismatch")

        approved_asset_ids = tuple(asset.asset_id for asset in approval.assets)
        if tuple(revision.asset_refs) != approved_asset_ids:
            raise PlatformSafeFailure("Approved asset set/order differs from revision authority")
        if len(approval.assets) > 1:
            raise PlatformSafeFailure("LinkedIn automatic V1 supports at most one approved image; use Manual Export")

        record = await self.production.get_artifact(tenant_id, revision.content_spec_ref)
        if record is None or record.get("digest") != approval.content_digest:
            raise PlatformSafeFailure("Approved ContentSpec persistence digest mismatch")
        try:
            content = ContentSpecV1.model_validate(record.get("payload"))
        except Exception as exc:
            raise PlatformSafeFailure("Approved ContentSpec payload is invalid") from exc
        if production_sha256(content) != approval.content_digest:
            raise PlatformSafeFailure("Approved ContentSpec canonical digest mismatch")
        commentary = _caption(content)
        if not commentary:
            raise PlatformSafeFailure("Approved ContentSpec contains no publishable commentary")

        if not approval.assets:
            return PreparedPublication(
                commentary=commentary,
                image_bytes=None,
                image_sha256=None,
                image_content_type=None,
                approval_bundle_sha256=approval.bundle_sha256,
            )

        approved_asset = approval.assets[0]
        asset = await self.rendering.get_asset(approved_asset.asset_id)
        if (
            asset is None
            or asset.tenant_id != tenant_id
            or asset.revision_id != approval.revision_id
            or asset.asset_id != approved_asset.asset_id
            or asset.page_index != 0
            or asset.sha256 != approved_asset.sha256
        ):
            raise PlatformSafeFailure("Approved AssetV1 lineage/hash metadata mismatch")
        try:
            data = await self.asset_store.get(asset.storage_key)
        except Exception as exc:
            raise PlatformSafeFailure("Approved asset bytes are unavailable") from exc
        actual = hashlib.sha256(data).hexdigest()
        if len(data) != asset.byte_size or actual != asset.sha256 or actual != approved_asset.sha256:
            raise PlatformSafeFailure("Approved asset bytes/hash changed after Approval")
        return PreparedPublication(
            commentary=commentary,
            image_bytes=data,
            image_sha256=actual,
            image_content_type=asset.content_type.value,
            approval_bundle_sha256=approval.bundle_sha256,
        )


class ScheduleDispatcher:
    """Mongo Schedule authority -> S9 durable outbox intent. It never calls LinkedIn."""

    JOB_KIND = "publish.linkedin.v1"

    def __init__(self, *, schedules, publications, connections, jobs):
        self.schedules = schedules
        self.publications = publications
        self.connections = connections
        self.jobs = jobs

    async def dispatch_due(self, *, tenant_id: str, now: datetime | None = None, limit: int = 100) -> int:
        now = now or utc_now()
        due = await self.schedules.list_due(now, limit=limit)
        dispatched = 0
        connection = await self.connections.get_linkedin()
        if connection is None:
            return 0
        for schedule in due:
            if schedule.tenant_id != tenant_id or schedule.provider != "linkedin":
                continue
            publication = PublicationV1(
                publication_id=deterministic_publication_id(schedule.job_key),
                tenant_id=tenant_id,
                approval_id=schedule.approval_id,
                schedule_id=schedule.schedule_id,
                provider="linkedin",
                connection_id=schedule.connection_id or connection["connection_id"],
                destination=schedule.destination,
                state=PublicationState.PENDING,
                idempotency_key=schedule.job_key,
                bundle_sha256=schedule.bundle_sha256,
            )
            publication = await self.publications.create(publication)
            payload = {
                "publication_id": publication.publication_id,
                "schedule_id": schedule.schedule_id,
                "approval_id": schedule.approval_id,
                "bundle_sha256": schedule.bundle_sha256,
                "provider": "linkedin",
                "destination": schedule.destination,
            }
            await self.jobs.enqueue(
                tenant_id=tenant_id,
                kind=self.JOB_KIND,
                idempotency_key=publication.idempotency_key,
                payload=payload,
            )
            moved = await self.schedules.mark_dispatched(schedule.schedule_id, now)
            if moved is not None:
                dispatched += 1
        return dispatched


class PublishWorkerHandler:
    """S10 business handler run only after S9 transport claim.

    A recovered domain `PUBLISHING` state becomes reconciliation. No external
    call can occur before a fresh atomic Publication PENDING -> PUBLISHING claim.
    """

    JOB_KIND = ScheduleDispatcher.JOB_KIND

    def __init__(self, *, publications, schedules, connections, builder, adapter):
        self.publications = publications
        self.schedules = schedules
        self.connections = connections
        self.builder = builder
        self.adapter = adapter

    async def __call__(self, job: JobIntent) -> None:
        if job.kind != self.JOB_KIND:
            raise ValueError("publish worker received unsupported job kind")
        publication_id = str(job.payload.get("publication_id") or "")
        if not publication_id:
            raise ValueError("publish job missing publication_id")
        publication = await self.publications.get(publication_id)
        if publication is None or publication.tenant_id != job.tenant_id:
            raise ValueError("publish job has no tenant-scoped Publication authority")
        if publication.bundle_sha256 != job.payload.get("bundle_sha256"):
            raise ValueError("publish job bundle digest differs from Publication authority")
        if publication.state in {
            PublicationState.PUBLISHED,
            PublicationState.FAILED_SAFE,
            PublicationState.RECONCILIATION_REQUIRED,
        }:
            return
        if publication.state is PublicationState.PUBLISHING:
            await self.publications.mark_reconciliation_required(
                publication.publication_id,
                attempt_id=publication.attempt_id,
                reason="Recovered PUBLISHING without durable receipt; automatic replay blocked",
                now=utc_now(),
                external_post_id=publication.external_post_id,
                external_asset_ids=publication.external_asset_ids,
            )
            return

        attempt_id = f"attempt_{uuid4().hex}"
        claim_status, claimed = await self.publications.claim(
            publication.publication_id,
            attempt_id=attempt_id,
            now=utc_now(),
        )
        if claim_status in {"ALREADY_PUBLISHED", "FAILED_SAFE", "RECONCILIATION_REQUIRED"}:
            return
        if claim_status == "PUBLISHING":
            await self.publications.mark_reconciliation_required(
                publication.publication_id,
                attempt_id=claimed.attempt_id if claimed else None,
                reason="Concurrent/recovered PUBLISHING claim requires reconciliation",
                now=utc_now(),
            )
            return
        if claim_status != "CLAIMED" or claimed is None:
            return

        connection = await self.connections.get_linkedin()
        if connection is None or connection.get("connection_id") != claimed.connection_id:
            failed = await self.publications.mark_failed_safe(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason="LinkedIn connection is unavailable",
                now=utc_now(),
            )
            if failed and claimed.schedule_id:
                await self.schedules.mark_failed(claimed.schedule_id, utc_now(), "LinkedIn connection is unavailable")
            return

        expected_identity = claimed.destination.rsplit("|", 1)[-1] if "|" in claimed.destination else ""
        if not expected_identity or connection.get("external_identity") != expected_identity:
            reason = "LinkedIn connection identity changed after scheduling; create a new schedule"
            failed = await self.publications.mark_failed_safe(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason=reason,
                now=utc_now(),
            )
            if failed and claimed.schedule_id:
                await self.schedules.mark_failed(claimed.schedule_id, utc_now(), reason)
            return

        try:
            prepared = await self.builder.build(tenant_id=job.tenant_id, publication=claimed)
            receipt = await self.adapter.publish(prepared, connection)
        except PlatformSafeFailure as exc:
            failed = await self.publications.mark_failed_safe(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason=str(exc),
                now=utc_now(),
            )
            if failed and claimed.schedule_id:
                await self.schedules.mark_failed(claimed.schedule_id, utc_now(), str(exc))
            return
        except PlatformUncertainFailure as exc:
            await self.publications.mark_reconciliation_required(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason=str(exc),
                now=utc_now(),
            )
            return

        try:
            published = await self.publications.mark_published(
                claimed.publication_id,
                attempt_id=attempt_id,
                receipt=receipt,
                now=utc_now(),
            )
        except Exception:
            await self.publications.mark_reconciliation_required(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason="Provider success observed but local receipt persistence raised; reconciliation required",
                now=utc_now(),
                external_post_id=receipt.external_post_id,
                external_asset_ids=receipt.external_asset_ids,
            )
            raise
        if published is None:
            await self.publications.mark_reconciliation_required(
                claimed.publication_id,
                attempt_id=attempt_id,
                reason="Provider success observed but publication CAS could not finalize",
                now=utc_now(),
                external_post_id=receipt.external_post_id,
                external_asset_ids=receipt.external_asset_ids,
            )
            return
        if published.schedule_id:
            await self.schedules.mark_completed(published.schedule_id, utc_now())


class CalendarService:
    def __init__(
        self,
        *,
        schedules,
        publications,
        connections,
        adapter,
        approval_reader=None,
        automatic_enabled: bool = True,
    ):
        self.schedules = schedules
        self.publications = publications
        self.connections = connections
        self.adapter = adapter
        self.approval_reader = approval_reader
        self.automatic_enabled = automatic_enabled

    async def view(self, *, start_at: datetime, end_at: datetime) -> dict:
        if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
            raise PublishingConflict("calendar range must be timezone-aware and increasing")
        schedules = await self.schedules.list_window(start_at.astimezone(timezone.utc), end_at.astimezone(timezone.utc))
        publications = await self.publications.list_for_schedules(
            [schedule.schedule_id for schedule in schedules]
        )
        by_schedule = {publication.schedule_id: publication for publication in publications if publication.schedule_id}
        connection = await self.connections.get_linkedin()
        capability = (
            await self.adapter.capabilities(connection)
            if connection
            else PlatformCapabilityV1(
                connected=False,
                can_publish=False,
                observed_at=utc_now(),
                reason="LinkedIn is not connected",
            )
        )
        if not self.automatic_enabled and capability.can_publish:
            capability = capability.model_copy(
                update={
                    "can_publish": False,
                    "reason": "Automatic publishing is disabled; Manual Export remains available",
                }
            )
        entries = []
        if self.approval_reader is not None:
            recent_approvals = await self.approval_reader.list_recent(limit=100)
            approval_ids = [item["approval_id"] for item in recent_approvals]
            historical_schedules = await self.schedules.list_for_approvals(approval_ids)
            occupied = {
                item.approval_id
                for item in historical_schedules
                if item.state is not ScheduleState.CANCELLED
            }
            for approval in recent_approvals:
                if approval["approval_id"] in occupied:
                    continue
                entries.append(
                    {
                        "kind": "approval",
                        "schedule_id": None,
                        "approval_id": approval["approval_id"],
                        "content_id": approval["content_id"],
                        "provider": "linkedin",
                        "destination": "member_feed",
                        "scheduled_for": None,
                        "approved_at": approval["approved_at"],
                        "timezone_context": None,
                        "state": "APPROVED_UNSCHEDULED",
                        "publication_id": None,
                        "reconciliation_reason": None,
                        "safe_error": None,
                        "asset_count": approval["asset_count"],
                    }
                )
        for schedule in schedules:
            publication = by_schedule.get(schedule.schedule_id)
            state = schedule.state.value
            if publication:
                state = publication.state.value
            entries.append(
                {
                    "kind": "schedule",
                    "schedule_id": schedule.schedule_id,
                    "approval_id": schedule.approval_id,
                    "provider": schedule.provider,
                    "destination": schedule.destination,
                    "scheduled_for": schedule.scheduled_for,
                    "timezone_context": schedule.timezone_context,
                    "state": state,
                    "publication_id": publication.publication_id if publication else None,
                    "reconciliation_reason": publication.reconciliation_reason if publication else None,
                    "safe_error": publication.safe_error if publication else schedule.failure_reason,
                }
            )
        return {
            "start_at": start_at,
            "end_at": end_at,
            "capability": capability.model_dump(mode="json"),
            "manual_export_fallback": True,
            "entries": entries,
        }
