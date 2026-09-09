from datetime import datetime, timezone

from application.quality.policy import (
    build_qa_report,
    evaluate_claim_consistency,
    evaluate_visual_observations,
    select_recovery,
)
from domain.production.models import (
    ClaimCategory,
    ClaimConfidence,
    ClaimPublishability,
    ClaimV1,
    ContentSpecV1,
    ResearchPackV1,
    ResearchVerdict,
    SingleImageSpecV1,
)
from domain.quality.models import QAVerdict, RecoveryAction, VisualQAObservationV1

DIGEST = "a" * 64


def _content(*claims: str) -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-1", plan_id="plan-1", language="es", hook="Hook", body="Body",
        format="single_image", format_spec=SingleImageSpecV1(headline="Headline"), claims_used=claims,
    )


def _research(*claims: ClaimV1) -> ResearchPackV1:
    return ResearchPackV1(research_id="research-1", plan_id="plan-1", verdict=ResearchVerdict.GO, claims=claims)


def _claim(claim_id: str, publishability: ClaimPublishability) -> ClaimV1:
    return ClaimV1(
        claim_id=claim_id, statement="Claim", category=ClaimCategory.FACTUAL,
        confidence=ClaimConfidence.HIGH, publishability=publishability,
    )


def _report(*, semantic=(), visual=()):
    return build_qa_report(
        qa_report_id="qa-1", tenant_id="tenant-1", revision_id="revision-1",
        content_spec_digest=DIGEST, render_input_digest=DIGEST, asset_digests=(DIGEST,),
        deterministic_checks=(), semantic_checks=semantic, visual_checks=visual,
        created_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )


def test_claim_mismatch_blocks_reviewable_boundary():
    checks = evaluate_claim_consistency(_content("missing"), _research())
    report = _report(semantic=checks)
    assert report.verdict == QAVerdict.FAIL
    assert report.failures == ("claim.unknown.missing",)
    assert select_recovery(report, attempt=0, budget=2).action == RecoveryAction.REWRITE_COPY


def test_forbidden_claim_blocks_even_when_claim_exists():
    checks = evaluate_claim_consistency(
        _content("c1"), _research(_claim("c1", ClaimPublishability.FORBIDDEN))
    )
    assert _report(semantic=checks).verdict == QAVerdict.FAIL


def test_clipping_auto_recovers_without_mutating_valid_copy_authority():
    checks = evaluate_visual_observations((VisualQAObservationV1(page_index=0, clipping=True),))
    report = _report(visual=checks)
    decision = select_recovery(report, attempt=0, budget=2)
    assert report.verdict == QAVerdict.FAIL
    assert decision.action == RecoveryAction.LAYOUT_RECOMPOSE
    assert decision.preserves_content is True
    assert decision.attempt == 1


def test_visual_failure_escalates_after_bounded_budget_and_preserves_upstream_work():
    checks = evaluate_visual_observations((VisualQAObservationV1(page_index=0, overlap=True),))
    report = _report(visual=checks)
    decision = select_recovery(report, attempt=2, budget=2)
    assert decision.action == RecoveryAction.ESCALATE
    assert decision.exhausted is True
    assert decision.preserves_content is True


def test_clean_visual_observation_passes():
    checks = evaluate_visual_observations((VisualQAObservationV1(page_index=0),))
    report = _report(visual=checks)
    assert report.verdict == QAVerdict.PASS
    assert select_recovery(report, attempt=0, budget=2).action == RecoveryAction.NONE
