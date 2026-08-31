from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.content_dyno import ContentDynoAnalyzer
from core.grounding import GroundingPolicy
from models.content_dyno import (
    DynoSignature,
    EditorialVerdict,
    HumanEditorialReview,
    TrustWheelStatus,
)
from models.content_run import ContentRun, VisualArtifactSnapshot
from models.grounding import (
    Claim,
    ClaimType,
    EvidenceBoundStatement,
    EvidenceRef,
    GroundingAssessment,
    GroundingDecision,
    GroundingReviewDecision,
    GroundingReviewSnapshot,
    GroundingStatus,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.value_engine import (
    AngleCandidate,
    AngleSelectionSnapshot,
    AttentionCriticAssessment,
    ContentFamily,
    ContentQualityDecision,
    ContentQualityGate,
    ContentQualitySnapshot,
)


HEX = "a" * 64
VISUAL_PROMPT = "technical editorial"


def _packet() -> SourcePacket:
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Dyno evidence",
        evidence=[
            EvidenceRef(
                evidence_id="ev-1",
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.USER_ASSERTION,
                excerpt="The server owns the renderer decision.",
            )
        ],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-1",
                statement="The server owns the renderer decision.",
                source_refs=["ev-1"],
            )
        ],
    )


def _quality(content: str) -> ContentQualitySnapshot:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assessment = AttentionCriticAssessment(
        assessment_id="critic-1",
        content_sha256=digest,
        critic_version="critic-v1",
        pass_number=1,
        hook=0.9,
        idea_clarity=0.9,
        novelty=0.8,
        specificity=0.9,
        credibility_signal=0.9,
        narrative_progression=0.85,
        payoff=0.9,
        human_voice=0.85,
        conversation_potential=0.8,
        profile_curiosity=0.85,
        spam_risk=0.0,
        ai_slop_risk=0.0,
    )
    gate = ContentQualityGate(
        policy_version="quality-v1",
        decision=ContentQualityDecision.PASS,
        editorial_score=0.87,
    )
    return ContentQualitySnapshot(
        content_sha256=digest,
        assessment=assessment,
        gate=gate,
    )


def _angle() -> AngleSelectionSnapshot:
    selected = AngleCandidate(
        candidate_id="angle-1",
        content_family=ContentFamily.ARCHITECTURE_DECISION,
        angle="The renderer choice is an architecture boundary, not prompt tuning.",
        hook_direction="A technical diagram should not depend on diffusion luck.",
        reader_tension="The prompt can be correct while the medium is wrong.",
        reader_payoff="Choose the renderer according to the communication job.",
        evidence_statement_refs=["fact-1"],
        audience_relevance=0.9,
        distinctiveness=0.9,
        specificity=0.9,
        profile_curiosity=0.8,
        evidence_density=0.9,
        spam_risk=0.0,
        ai_slop_risk=0.0,
    )
    return AngleSelectionSnapshot(
        selection_id="selection-1",
        output_id="output-1",
        selected_candidate_id="angle-1",
        selection_policy_version="angle-selection-policy-v1",
        selected_score=0.9,
        selected_candidate=selected,
        alternatives=[],
        idea_sha256=HEX,
        research_sha256=HEX,
        factual_envelope_sha256=HEX,
    )


def _human(
    run: ContentRun,
    verdict: EditorialVerdict = EditorialVerdict.WOULD_PUBLISH_NOW,
) -> HumanEditorialReview:
    assert run.final_content is not None
    assert run.visual_render is not None
    assert run.visual_render.asset_sha256 is not None
    return HumanEditorialReview(
        run_id=run.run_id,
        final_content_sha256=hashlib.sha256(run.final_content.encode("utf-8")).hexdigest(),
        visual_asset_sha256=run.visual_render.asset_sha256,
        topic_fidelity=0.9,
        pov_strength=0.9,
        human_voice=0.9,
        usefulness=0.9,
        visual_message_fit=0.9,
        publish_readiness=0.9,
        verdict=verdict,
        notes=["Would publish without manual rewriting."],
    )


def _signed_run(*, trust_decision: GroundingDecision = GroundingDecision.PASS) -> ContentRun:
    content = (
        "La arquitectura visual falla cuando elegimos el renderer por costumbre. "
        "El servidor decide el renderer y reserva la generación para ilustraciones."
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    packet = _packet()
    assessment = GroundingAssessment(
        assessment_id="assessment-1",
        packet_id=packet.packet_id,
        content_sha256=digest,
        evaluator_version="grounding-assessment-builder-v1",
        extraction_complete=True,
        claims=[
            Claim(
                claim_id="claim-1",
                statement="El servidor decide el renderer.",
                claim_type=ClaimType.FACT,
                grounding_status=(
                    GroundingStatus.GROUNDED
                    if trust_decision == GroundingDecision.PASS
                    else GroundingStatus.INSUFFICIENT_EVIDENCE
                ),
                source_refs=["ev-1"] if trust_decision == GroundingDecision.PASS else [],
                confidence=1.0,
            )
        ],
    )
    gate = GroundingPolicy.evaluate(assessment, packet)
    assert gate.decision == trust_decision
    review = GroundingReviewSnapshot(
        review_id="review-1",
        decision=GroundingReviewDecision.VERIFIED,
        content_sha256=digest,
        source_packet_sha256=ContentDynoAnalyzer._sha256_json(packet.model_dump(mode="python")),
        assessment_sha256=ContentDynoAnalyzer._sha256_json(assessment.model_dump(mode="python")),
        policy_version=gate.policy_version,
    )
    visual = VisualArtifactSnapshot(
        render_id="render-1",
        status="READY",
        provider="DeterministicBrowserRenderer",
        asset_url="/assets/renders/render-1.png",
        asset_sha256=HEX,
        width=1080,
        height=1350,
        prompt_used=VISUAL_PROMPT,
        requested_prompt=VISUAL_PROMPT,
        aspect_ratio="4:5",
        style="technical_editorial",
        idempotency_key="dyno-render-1",
    )
    return ContentRun(
        run_id="run-1",
        workspace_id="workspace-1",
        topic="Por qué un renderer es una decisión de arquitectura",
        style="educational",
        idea="Renderer choice is an architecture boundary.",
        content_profile_id="profile-1",
        generation_source_packet=packet,
        angle_selection=_angle(),
        content_quality=_quality(content),
        final_status="READY",
        final_content=content,
        visual_prompt=VISUAL_PROMPT,
        visual_render=visual,
        source_packet=packet,
        grounding_assessment=assessment,
        grounding_gate=gate,
        grounding_review=review,
    )


def test_signed_pass_requires_trust_human_publish_now_and_no_high_losses():
    run = _signed_run()
    report = ContentDynoAnalyzer.analyze(run, _human(run))
    assert report.trust_at_wheels.status == TrustWheelStatus.PASS
    assert report.signature == DynoSignature.SIGNED_PASS
    assert not [loss for loss in report.drivetrain_losses if loss.severity.value == "HIGH"]


def test_trust_fail_cannot_be_overridden_by_strong_human_review():
    run = _signed_run(trust_decision=GroundingDecision.BLOCK)
    report = ContentDynoAnalyzer.analyze(run, _human(run))
    assert report.trust_at_wheels.status == TrustWheelStatus.FAIL
    assert report.signature == DynoSignature.TRUST_FAIL
    assert "TRUST_FAIL" in {loss.code for loss in report.drivetrain_losses}


def test_stale_human_grounding_review_cannot_produce_trust_pass():
    run = _signed_run()
    human = _human(run)
    run.source_packet.title = "Evidence changed after human verification"
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.trust_at_wheels.status == TrustWheelStatus.NOT_MEASURED
    assert report.signature == DynoSignature.UNSIGNED
    assert "TRUST_NOT_MEASURED" in {loss.code for loss in report.drivetrain_losses}


def test_stale_editorial_sensor_snapshot_is_a_high_drivetrain_loss():
    run = _signed_run()
    human = _human(run)
    run.content_quality.content_sha256 = "b" * 64
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.signature == DynoSignature.UNSIGNED
    assert "ATTENTION_CRITIC_STALE" in {loss.code for loss in report.drivetrain_losses}


def test_would_publish_now_cannot_hide_weak_human_dimensions():
    run = _signed_run()
    human = _human(run)
    human.visual_message_fit = 0.35
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.signature == DynoSignature.UNSIGNED
    assert "VISUAL_MESSAGE_FIT_LOW" in {loss.code for loss in report.drivetrain_losses}


def test_publishable_is_not_equivalent_to_would_publish_now():
    run = _signed_run()
    report = ContentDynoAnalyzer.analyze(
        run,
        _human(run, EditorialVerdict.PUBLISHABLE),
    )
    assert report.signature == DynoSignature.UNSIGNED
    assert "NOT_WOULD_PUBLISH_NOW" in {loss.code for loss in report.drivetrain_losses}


def test_human_editorial_review_is_bound_to_exact_run_id():
    run = _signed_run()
    human = _human(run)
    human.run_id = "different-run"
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.signature == DynoSignature.UNSIGNED
    assert "HUMAN_EDITORIAL_REVIEW_RUN_MISMATCH" in {
        loss.code for loss in report.drivetrain_losses
    }


def test_human_editorial_review_is_bound_to_exact_content_revision():
    run = _signed_run()
    human = _human(run)
    run.final_content = f"{run.final_content} Cambio posterior."
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.signature == DynoSignature.UNSIGNED
    assert "HUMAN_EDITORIAL_REVIEW_CONTENT_STALE" in {
        loss.code for loss in report.drivetrain_losses
    }


def test_human_editorial_review_is_bound_to_exact_visual_asset():
    run = _signed_run()
    human = _human(run)
    run.visual_render.asset_sha256 = "b" * 64
    report = ContentDynoAnalyzer.analyze(run, human)
    assert report.signature == DynoSignature.UNSIGNED
    assert "HUMAN_EDITORIAL_REVIEW_VISUAL_STALE" in {
        loss.code for loss in report.drivetrain_losses
    }


def test_missing_evidence_profile_and_visual_are_visible_drivetrain_losses():
    run = ContentRun(
        run_id="run-lossy",
        workspace_id="workspace-1",
        topic="Generic topic",
        style="educational",
        idea="Generic idea",
        final_status="NEEDS_CONTENT_REVIEW",
        final_content="A generic technical post.",
    )
    report = ContentDynoAnalyzer.analyze(run)
    codes = {loss.code for loss in report.drivetrain_losses}
    assert {
        "EVIDENCE_ABSENT",
        "PROFILE_ABSENT",
        "ANGLE_ENGINE_UNMEASURED_OR_DEGRADED",
        "ATTENTION_CRITIC_UNMEASURED_OR_DEGRADED",
        "FINAL_VISUAL_NOT_RENDERED",
        "TRUST_NOT_MEASURED",
        "HUMAN_EDITORIAL_REVIEW_MISSING",
    }.issubset(codes)
    assert report.signature == DynoSignature.UNSIGNED


def test_batch_report_never_collapses_trust_and_editorial_into_combined_score():
    signed_run = _signed_run()
    unsigned_run = _signed_run()
    signed = ContentDynoAnalyzer.analyze(signed_run, _human(signed_run))
    unsigned = ContentDynoAnalyzer.analyze(
        unsigned_run,
        _human(unsigned_run, EditorialVerdict.STRONG),
    )
    batch = ContentDynoAnalyzer.batch([signed, unsigned])
    payload = batch.model_dump(mode="json")
    assert batch.case_count == 2
    assert batch.signed_pass_count == 1
    assert batch.would_publish_now_rate == 0.5
    assert "combined_score" not in payload
    assert "wheel_hp" not in payload


def test_stale_publish_now_review_does_not_count_toward_batch_rate():
    current_run = _signed_run()
    stale_run = _signed_run()
    current = ContentDynoAnalyzer.analyze(current_run, _human(current_run))
    stale_human = _human(stale_run)
    stale_run.visual_render.asset_sha256 = "c" * 64
    stale = ContentDynoAnalyzer.analyze(stale_run, stale_human)

    batch = ContentDynoAnalyzer.batch([current, stale])
    assert batch.would_publish_now_count == 1
    assert batch.would_publish_now_rate == 0.5
    assert batch.loss_frequency["HUMAN_EDITORIAL_REVIEW_VISUAL_STALE"] == 1


def test_content_dyno_plan_contains_five_real_evidence_fed_cases():
    path = Path(__file__).resolve().parents[1] / "golden" / "content_dyno_v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) == 5
    assert len({case["case_id"] for case in cases}) == 5
    assert all(len(case["source_assertions"]) >= 4 for case in cases)
    assert all(case["review_focus"] for case in cases)
