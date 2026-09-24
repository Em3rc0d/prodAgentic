from __future__ import annotations

from application.content_quality.policy import factual_precision_issues, strict_publishability_issues
from application.production.service import ProductionContractViolation, StructuredAgentCellService
from domain.production.models import EditorialVerdict


class R4StructuredAgentCellService(StructuredAgentCellService):
    """Real-provider R4 text production with a stricter publishability floor.

    Demo/certification keeps the base S3 service so deterministic fixtures remain
    provider-free. Production uses this subclass, which promotes known generic
    template/value-density warnings to fail-closed contract violations if an
    Editor model incorrectly tries to approve them.
    """

    def __init__(self, *, evidence_provider, **kwargs):
        if evidence_provider is None:
            raise ValueError("R4.1 production requires an EvidenceAcquisitionPort")
        super().__init__(evidence_provider=evidence_provider, **kwargs)

    @classmethod
    def _verify_review(cls, plan, profile, research, content, review) -> None:
        super()._verify_review(plan, profile, research, content, review)
        if review.verdict != EditorialVerdict.APPROVE_TEXT:
            return
        issues = (
            strict_publishability_issues(content=content, plan=plan, profile=profile)
            + factual_precision_issues(content=content, research=research)
        )
        if issues:
            codes = ", ".join(issue.code for issue in issues)
            raise ProductionContractViolation(
                f"R4 APPROVE_TEXT violates strict publishability: {codes}"
            )
