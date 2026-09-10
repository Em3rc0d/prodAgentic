from __future__ import annotations

from typing import Protocol

from domain.production.models import ContentRevisionV1, GenerationRunV1
from domain.quality.models import QAReportV1, VisualQAObservationV1
from domain.rendering.models import RendererRequestV1


class QualityRepositoryPort(Protocol):
    async def save_report(self, report: QAReportV1) -> None: ...

    async def get_report(self, tenant_id: str, qa_report_id: str) -> QAReportV1 | None: ...

    async def get_latest_report_by_revision(
        self, tenant_id: str, revision_id: str
    ) -> QAReportV1 | None: ...

    async def claim_text_revision_qa(
        self,
        *,
        revision_id: str,
        run_id: str,
        expected_content_spec_digest: str,
    ) -> tuple[ContentRevisionV1, GenerationRunV1] | None: ...

    async def mark_revision_reviewable(
        self,
        *,
        revision_id: str,
        qa_report: QAReportV1,
        expected_asset_refs: tuple[str, ...],
        expected_content_spec_digest: str,
        expected_visual_spec_digest: str | None,
    ) -> ContentRevisionV1 | None: ...

    async def finish_run_completed(
        self,
        *,
        run_id: str,
        revision_id: str,
        qa_report_id: str,
    ) -> GenerationRunV1 | None: ...


class VisualQualityInspectorPort(Protocol):
    async def inspect(self, request: RendererRequestV1) -> tuple[VisualQAObservationV1, ...]: ...
