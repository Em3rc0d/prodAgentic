from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.production.models import (
    ContentRevisionV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionStatus,
    utc_now,
)
from domain.quality.models import QAReportV1, QAVerdict, canonical_qa_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


def _hydrate_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return {key: _hydrate_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_hydrate_utc(item) for item in value]
    return value


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    value.pop("metadata_digest", None)
    return _hydrate_utc(value)


def _report_digest(report: QAReportV1) -> str:
    return canonical_qa_sha256(report.model_dump(mode="json", exclude={"digest"}))


class MongoQualityRepository:
    """S6 durable QA authority with tenant scope and idempotent CAS transitions."""

    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.reports = TenantScopedMongoRepository(db, "qa_reports", context)
        self.revisions = TenantScopedMongoRepository(db, "content_revisions", context)
        self.runs = TenantScopedMongoRepository(db, "generation_runs", context)

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.context.tenant_id:
            raise ValueError("Quality repository tenant authority mismatch")

    async def save_report(self, report: QAReportV1) -> None:
        self._require_tenant(report.tenant_id)
        if _report_digest(report) != report.digest:
            raise ValueError("QAReportV1 digest mismatch")
        existing = await self.get_report(report.tenant_id, report.qa_report_id)
        if existing is not None:
            if existing != report:
                raise ValueError("QAReportV1 identity collision")
            return
        payload = report.model_dump()
        payload["metadata_digest"] = report.digest
        await self.reports.insert_one(payload)

    async def get_report(self, tenant_id: str, qa_report_id: str) -> QAReportV1 | None:
        self._require_tenant(tenant_id)
        raw = await self.reports.find_one({"qa_report_id": qa_report_id})
        if raw is None:
            return None
        stored_digest = raw.get("metadata_digest")
        report = QAReportV1.model_validate(_clean(raw))
        if stored_digest != report.digest or _report_digest(report) != report.digest:
            raise ValueError("persisted QAReportV1 digest mismatch")
        return report

    async def mark_revision_reviewable(
        self,
        *,
        revision_id: str,
        qa_report: QAReportV1,
        expected_asset_refs: tuple[str, ...],
        expected_content_spec_digest: str,
        expected_visual_spec_digest: str | None,
    ) -> ContentRevisionV1 | None:
        self._require_tenant(qa_report.tenant_id)
        if qa_report.revision_id != revision_id:
            raise ValueError("QAReportV1 revision authority mismatch")
        if qa_report.verdict == QAVerdict.FAIL:
            raise ValueError("failing QAReportV1 cannot make a revision reviewable")
        persisted_report = await self.get_report(qa_report.tenant_id, qa_report.qa_report_id)
        if persisted_report != qa_report:
            raise ValueError("QAReportV1 must be durably persisted before reviewable transition")

        criteria: dict[str, Any] = {
            "revision_id": revision_id,
            "status": RevisionStatus.QA_PENDING.value,
            "qa_report_id": None,
            "asset_refs": list(expected_asset_refs),
            "content_spec_digest": expected_content_spec_digest,
            "visual_spec_digest": expected_visual_spec_digest,
        }
        result = await self.revisions.update_one(
            criteria,
            {"$set": {"qa_report_id": qa_report.qa_report_id, "status": RevisionStatus.REVIEWABLE.value}},
        )
        document = await self.revisions.find_one({"revision_id": revision_id})
        cleaned = _hydrate_utc({key: value for key, value in document.items() if key != "_id"}) if document else None
        if result.matched_count == 1:
            return ContentRevisionV1.model_validate(cleaned) if cleaned else None
        if cleaned is None:
            return None
        existing = ContentRevisionV1.model_validate(cleaned)
        if (
            existing.status == RevisionStatus.REVIEWABLE
            and existing.qa_report_id == qa_report.qa_report_id
            and existing.asset_refs == expected_asset_refs
            and existing.content_spec_digest == expected_content_spec_digest
            and existing.visual_spec_digest == expected_visual_spec_digest
        ):
            return existing
        return None

    async def finish_run_completed(
        self,
        *,
        run_id: str,
        revision_id: str,
        qa_report_id: str,
    ) -> GenerationRunV1 | None:
        revision_document = await self.revisions.find_one({"revision_id": revision_id})
        if revision_document is None:
            return None
        revision = ContentRevisionV1.model_validate(
            _hydrate_utc({key: value for key, value in revision_document.items() if key != "_id"})
        )
        if revision.run_id != run_id or revision.status != RevisionStatus.REVIEWABLE or revision.qa_report_id != qa_report_id:
            return None

        result = await self.runs.update_one(
            {"run_id": run_id, "state": GenerationRunState.QA.value},
            {
                "$set": {"state": GenerationRunState.COMPLETED.value, "failure": None, "completed_at": utc_now()},
                "$addToSet": {"qa_report_refs": qa_report_id},
            },
        )
        document = await self.runs.find_one({"run_id": run_id})
        cleaned = _hydrate_utc({key: value for key, value in document.items() if key != "_id"}) if document else None
        if result.matched_count == 1:
            return GenerationRunV1.model_validate(cleaned) if cleaned else None
        if cleaned is None:
            return None
        existing = GenerationRunV1.model_validate(cleaned)
        if (
            existing.state == GenerationRunState.COMPLETED
            and qa_report_id in existing.qa_report_refs
            and existing.completed_at is not None
        ):
            return existing
        return None
