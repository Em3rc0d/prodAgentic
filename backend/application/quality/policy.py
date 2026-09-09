from __future__ import annotations

from datetime import datetime, timezone

from domain.production.models import ClaimPublishability, ContentSpecV1, ResearchPackV1
from domain.quality.models import (
    QACheckLayer,
    QACheckV1,
    QAReportV1,
    QASeverity,
    QAVerdict,
    RecoveryAction,
    RecoveryDecisionV1,
    VisualQAObservationV1,
    canonical_qa_sha256,
)
from domain.rendering.models import RenderResultV1


def evaluate_claim_consistency(content: ContentSpecV1, research: ResearchPackV1) -> tuple[QACheckV1, ...]:
    claims = {claim.claim_id: claim for claim in research.claims}
    checks: list[QACheckV1] = []
    for claim_id in content.claims_used:
        claim = claims.get(claim_id)
        if claim is None:
            checks.append(QACheckV1(
                code=f"claim.unknown.{claim_id}", layer=QACheckLayer.SEMANTIC,
                severity=QASeverity.BLOCKING, passed=False,
                message="Content references a claim absent from the authoritative ResearchPack.",
                target_ref=claim_id, recovery_hint=RecoveryAction.REWRITE_COPY,
            ))
            continue
        if claim.publishability == ClaimPublishability.FORBIDDEN:
            checks.append(QACheckV1(
                code=f"claim.forbidden.{claim_id}", layer=QACheckLayer.SEMANTIC,
                severity=QASeverity.BLOCKING, passed=False,
                message="Content uses a ResearchPack claim marked forbidden for publication.",
                target_ref=claim_id, recovery_hint=RecoveryAction.REWRITE_COPY,
            ))
        elif claim.publishability == ClaimPublishability.QUALIFY:
            checks.append(QACheckV1(
                code=f"claim.qualify.{claim_id}", layer=QACheckLayer.SEMANTIC,
                severity=QASeverity.WARNING, passed=False,
                message="Claim is publishable only with qualification; retain warning for human review.",
                target_ref=claim_id, recovery_hint=RecoveryAction.NONE,
            ))
        else:
            checks.append(QACheckV1(
                code=f"claim.allowed.{claim_id}", layer=QACheckLayer.SEMANTIC,
                severity=QASeverity.INFO, passed=True,
                message="Claim is present in ResearchPack and allowed for publication.",
                target_ref=claim_id,
            ))
    return tuple(checks)


def evaluate_render_integrity(render: RenderResultV1, expected_asset_refs: tuple[str, ...]) -> tuple[QACheckV1, ...]:
    actual = tuple(asset.asset_id for asset in render.assets)
    checks = [QACheckV1(
        code="asset.refs.exact",
        layer=QACheckLayer.DETERMINISTIC,
        severity=QASeverity.BLOCKING,
        passed=actual == expected_asset_refs,
        message="Revision asset refs must exactly match the deterministic RenderResult asset set.",
        recovery_hint=RecoveryAction.VISUAL_REGEN,
    )]
    for asset in render.assets:
        checks.append(QACheckV1(
            code=f"asset.metadata.{asset.page_index}",
            layer=QACheckLayer.DETERMINISTIC,
            severity=QASeverity.BLOCKING,
            passed=asset.width > 0 and asset.height > 0 and asset.byte_size > 0 and len(asset.sha256) == 64,
            message="Owned render asset exposes valid dimensions, byte size and SHA-256 metadata.",
            target_ref=asset.asset_id,
            recovery_hint=RecoveryAction.VISUAL_REGEN,
        ))
    return tuple(checks)


def evaluate_visual_observations(observations: tuple[VisualQAObservationV1, ...]) -> tuple[QACheckV1, ...]:
    checks: list[QACheckV1] = []
    fields = (
        ("clipping", "visual.clipping", RecoveryAction.LAYOUT_RECOMPOSE),
        ("overlap", "visual.overlap", RecoveryAction.LAYOUT_RECOMPOSE),
        ("unreadable_hierarchy", "visual.hierarchy", RecoveryAction.LAYOUT_RECOMPOSE),
        ("malformed_imagery", "visual.malformed", RecoveryAction.VISUAL_REGEN),
        ("wrong_visible_text", "visual.wrong_text", RecoveryAction.VISUAL_REGEN),
        ("key_copy_omitted", "visual.copy_omitted", RecoveryAction.VISUAL_REGEN),
        ("duplicate_page", "visual.duplicate_page", RecoveryAction.VISUAL_REGEN),
        ("semantic_contradiction", "visual.semantic_contradiction", RecoveryAction.VISUAL_REGEN),
    )
    for observation in observations:
        for field, code, hint in fields:
            failed = bool(getattr(observation, field))
            checks.append(QACheckV1(
                code=f"{code}.p{observation.page_index}",
                layer=QACheckLayer.VISUAL,
                severity=QASeverity.BLOCKING,
                passed=not failed,
                message=f"Page {observation.page_index} check: {field.replace('_', ' ')}.",
                target_ref=f"page:{observation.page_index}",
                recovery_hint=hint if failed else RecoveryAction.NONE,
            ))
    return tuple(checks)


def build_qa_report(*, qa_report_id: str, tenant_id: str, revision_id: str,
                    content_spec_digest: str, render_input_digest: str | None,
                    asset_digests: tuple[str, ...], deterministic_checks: tuple[QACheckV1, ...],
                    semantic_checks: tuple[QACheckV1, ...], visual_checks: tuple[QACheckV1, ...],
                    recovery_attempt: int = 0, created_at: datetime | None = None) -> QAReportV1:
    checks = deterministic_checks + semantic_checks + visual_checks
    failures = tuple(c.code for c in checks if not c.passed and c.severity == QASeverity.BLOCKING)
    warnings = tuple(c.code for c in checks if not c.passed and c.severity == QASeverity.WARNING)
    verdict = QAVerdict.FAIL if failures else QAVerdict.PASS_WITH_WARNINGS if warnings else QAVerdict.PASS
    base = {
        "schema_version": 1, "qa_report_id": qa_report_id, "tenant_id": tenant_id,
        "revision_id": revision_id, "policy_version": "qa-policy-v1",
        "deterministic_checks": deterministic_checks, "semantic_checks": semantic_checks,
        "visual_checks": visual_checks, "warnings": warnings, "failures": failures,
        "verdict": verdict, "content_spec_digest": content_spec_digest,
        "render_input_digest": render_input_digest, "asset_digests": asset_digests,
        "recovery_attempt": recovery_attempt, "created_at": created_at or datetime.now(timezone.utc),
    }
    digest = canonical_qa_sha256(base)
    return QAReportV1(**base, digest=digest)


def select_recovery(report: QAReportV1, *, attempt: int, budget: int) -> RecoveryDecisionV1:
    failed = report.deterministic_checks + report.semantic_checks + report.visual_checks
    hints = {check.recovery_hint for check in failed if not check.passed and check.severity == QASeverity.BLOCKING}
    if not hints:
        return RecoveryDecisionV1(action=RecoveryAction.NONE, attempt=attempt, budget=budget,
                                  exhausted=False, preserves_content=True, reason="No blocking QA failure.")
    if attempt >= budget:
        return RecoveryDecisionV1(action=RecoveryAction.ESCALATE, attempt=attempt, budget=budget,
                                  exhausted=True, preserves_content=True,
                                  reason="Automatic recovery budget exhausted; retain valid upstream work for user attention.")
    if hints <= {RecoveryAction.LAYOUT_RECOMPOSE}:
        return RecoveryDecisionV1(action=RecoveryAction.LAYOUT_RECOMPOSE, attempt=attempt + 1, budget=budget,
                                  exhausted=False, preserves_content=True,
                                  reason="Visual geometry failure can be recomposed without changing valid copy authority.")
    if RecoveryAction.REWRITE_COPY in hints:
        return RecoveryDecisionV1(action=RecoveryAction.REWRITE_COPY, attempt=attempt + 1, budget=budget,
                                  exhausted=False, preserves_content=False,
                                  reason="Semantic claim failure requires a bounded copy revision.")
    return RecoveryDecisionV1(action=RecoveryAction.VISUAL_REGEN, attempt=attempt + 1, budget=budget,
                              exhausted=False, preserves_content=True,
                              reason="Visual-only failure requires regeneration while preserving valid content.")
