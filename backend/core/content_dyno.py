from __future__ import annotations

import hashlib
from collections import Counter

from core.visual_direction import VisualDirectionPolicy, VisualRenderer
from models.content_dyno import (
    ContentDynoBatchReport,
    ContentDynoCaseReport,
    DrivetrainLoss,
    DynoSignature,
    EditorialSensorSnapshot,
    EditorialVerdict,
    HumanEditorialReview,
    LossSeverity,
    TrustWheelReport,
    TrustWheelStatus,
)
from models.content_run import ContentRun, StageStatus


class ContentDynoAnalyzer:
    """Deterministic product-output dyno.

    Internal model scores are preserved as advisory sensors. They never become
    the human editorial verdict and they never compensate for factual failure.
    """

    VERSION = "content-dyno-v1"

    @staticmethod
    def _enum_value(value) -> str | None:
        if value is None:
            return None
        return getattr(value, "value", str(value))

    @staticmethod
    def _sha256(value: str | None) -> str | None:
        if value is None:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _editorial_sensors(cls, run: ContentRun) -> EditorialSensorSnapshot:
        quality = run.content_quality
        if quality is None:
            return EditorialSensorSnapshot()
        assessment = quality.assessment
        gate = quality.gate
        return EditorialSensorSnapshot(
            editorial_score=gate.editorial_score,
            decision=cls._enum_value(gate.decision),
            pass_number=assessment.pass_number,
            hook=assessment.hook,
            idea_clarity=assessment.idea_clarity,
            novelty=assessment.novelty,
            specificity=assessment.specificity,
            credibility_signal=assessment.credibility_signal,
            narrative_progression=assessment.narrative_progression,
            payoff=assessment.payoff,
            human_voice=assessment.human_voice,
            conversation_potential=assessment.conversation_potential,
            profile_curiosity=assessment.profile_curiosity,
            spam_risk=assessment.spam_risk,
            ai_slop_risk=assessment.ai_slop_risk,
            hard_flags=list(gate.hard_flags),
        )

    @classmethod
    def _trust_report(cls, run: ContentRun) -> TrustWheelReport:
        gate = run.grounding_gate
        review = run.grounding_review
        assessment = run.grounding_assessment
        packet = run.source_packet

        if packet is None or assessment is None or gate is None:
            return TrustWheelReport(
                status=TrustWheelStatus.NOT_MEASURED,
                reasons=[
                    "Final Grounding has not completed against an authoritative SourcePacket."
                ],
            )

        gate_decision = cls._enum_value(gate.decision)
        review_decision = cls._enum_value(review.decision) if review is not None else None
        human_verified = review_decision == "VERIFIED"

        if gate_decision != "PASS":
            return TrustWheelReport(
                status=TrustWheelStatus.FAIL,
                grounding_decision=gate_decision,
                grounding_policy_version=gate.policy_version,
                human_grounding_verified=human_verified,
                blocking_claim_ids=list(gate.blocking_claim_ids),
                warning_claim_ids=list(gate.warning_claim_ids),
                reasons=list(gate.reasons),
            )

        if not human_verified:
            return TrustWheelReport(
                status=TrustWheelStatus.NOT_MEASURED,
                grounding_decision=gate_decision,
                grounding_policy_version=gate.policy_version,
                human_grounding_verified=False,
                blocking_claim_ids=list(gate.blocking_claim_ids),
                warning_claim_ids=list(gate.warning_claim_ids),
                reasons=[
                    "Deterministic Grounding passed, but explicit human Grounding verification is missing."
                ],
            )

        return TrustWheelReport(
            status=TrustWheelStatus.PASS,
            grounding_decision=gate_decision,
            grounding_policy_version=gate.policy_version,
            human_grounding_verified=True,
            blocking_claim_ids=list(gate.blocking_claim_ids),
            warning_claim_ids=list(gate.warning_claim_ids),
            reasons=list(gate.reasons),
        )

    @classmethod
    def _losses(
        cls,
        run: ContentRun,
        human_review: HumanEditorialReview | None,
        trust: TrustWheelReport,
    ) -> list[DrivetrainLoss]:
        losses: list[DrivetrainLoss] = []

        def add(code: str, layer: str, severity: LossSeverity, detail: str) -> None:
            losses.append(
                DrivetrainLoss(
                    code=code,
                    layer=layer,
                    severity=severity,
                    detail=detail,
                )
            )

        if run.generation_source_packet is None:
            add(
                "EVIDENCE_ABSENT",
                "fuel",
                LossSeverity.HIGH,
                "Generation ran without an immutable pre-generation SourcePacket.",
            )
        if run.content_profile_id is None:
            add(
                "PROFILE_ABSENT",
                "voice",
                LossSeverity.MEDIUM,
                "No content profile was bound to the run, so recognizable voice is not being measured at full fidelity.",
            )
        if run.angle_selection is None:
            add(
                "ANGLE_ENGINE_UNMEASURED_OR_DEGRADED",
                "value_engine",
                LossSeverity.HIGH,
                "No persisted angle selection exists for this run.",
            )
        if run.content_quality is None:
            add(
                "ATTENTION_CRITIC_UNMEASURED_OR_DEGRADED",
                "value_engine",
                LossSeverity.HIGH,
                "No persisted Attention Critic snapshot exists for the final content.",
            )
        else:
            if cls._enum_value(run.content_quality.gate.decision) != "PASS":
                add(
                    "EDITORIAL_GATE_NOT_PASSING",
                    "value_engine",
                    LossSeverity.HIGH,
                    "The final advisory editorial gate still requests another rewrite/review.",
                )
            if run.content_quality.rewrite_performed:
                add(
                    "AUTO_REWRITE_REQUIRED",
                    "editorial_transmission",
                    LossSeverity.MEDIUM,
                    "The first edited output did not clear the editorial gate and required the single automatic rewrite.",
                )

        if run.final_status != "READY":
            add(
                "FINAL_STATUS_REQUIRES_REVIEW",
                "editorial_transmission",
                LossSeverity.HIGH,
                f"Pipeline final_status is {run.final_status or 'UNKNOWN'} rather than READY.",
            )

        for stage_name, stage in run.stages.items():
            if stage.attempt_failures > 0:
                add(
                    "PROVIDER_ATTEMPT_FAILURE",
                    stage_name,
                    LossSeverity.MEDIUM,
                    f"Stage {stage_name} recorded {stage.attempt_failures} failed provider attempt(s).",
                )
            if stage.status == StageStatus.FAILED and stage_name != "visual":
                add(
                    "STAGE_FAILED",
                    stage_name,
                    LossSeverity.HIGH,
                    f"Authoritative stage {stage_name} is FAILED.",
                )

        if not run.final_content:
            add(
                "FINAL_CONTENT_MISSING",
                "output",
                LossSeverity.HIGH,
                "No final content exists to evaluate.",
            )

        if run.visual_render is None:
            add(
                "FINAL_VISUAL_NOT_RENDERED",
                "visual",
                LossSeverity.HIGH,
                "The product dyno measures the final editorial asset, not only a visual prompt.",
            )
        else:
            if run.visual_render.status != "READY":
                add(
                    "FINAL_VISUAL_NOT_READY",
                    "visual",
                    LossSeverity.HIGH,
                    f"Visual render status is {run.visual_render.status}.",
                )
            if run.final_content:
                expected = VisualDirectionPolicy.select(run.final_content, style=run.style)
                actual_provider = run.visual_render.provider
                deterministic = actual_provider == "DeterministicBrowserRenderer"
                if expected.renderer == VisualRenderer.DETERMINISTIC and not deterministic:
                    add(
                        "VISUAL_RENDERER_MISMATCH",
                        "visual",
                        LossSeverity.HIGH,
                        "A technical/editorial format reached a generative renderer instead of the deterministic renderer.",
                    )
                if expected.renderer == VisualRenderer.GENERATIVE and deterministic:
                    add(
                        "VISUAL_RENDERER_MISMATCH",
                        "visual",
                        LossSeverity.MEDIUM,
                        "An illustration-class visual was rendered through the deterministic renderer.",
                    )

        if trust.status == TrustWheelStatus.NOT_MEASURED:
            add(
                "TRUST_NOT_MEASURED",
                "trust",
                LossSeverity.HIGH,
                "Trust @ Wheels is incomplete: final Grounding plus explicit human verification are required.",
            )
        elif trust.status == TrustWheelStatus.FAIL:
            add(
                "TRUST_FAIL",
                "trust",
                LossSeverity.HIGH,
                "Trust @ Wheels failed. Editorial strength cannot compensate for factual failure.",
            )

        if human_review is None:
            add(
                "HUMAN_EDITORIAL_REVIEW_MISSING",
                "human_dyno",
                LossSeverity.HIGH,
                "The final publishability verdict must come from explicit human review.",
            )
        elif human_review.verdict != EditorialVerdict.WOULD_PUBLISH_NOW:
            add(
                "NOT_WOULD_PUBLISH_NOW",
                "human_dyno",
                LossSeverity.HIGH,
                f"Human verdict is {human_review.verdict.value}, not WOULD_PUBLISH_NOW.",
            )

        return losses

    @classmethod
    def analyze(
        cls,
        run: ContentRun,
        human_review: HumanEditorialReview | None = None,
    ) -> ContentDynoCaseReport:
        trust = cls._trust_report(run)
        losses = cls._losses(run, human_review, trust)
        high_losses = [loss for loss in losses if loss.severity == LossSeverity.HIGH]

        if trust.status == TrustWheelStatus.FAIL:
            signature = DynoSignature.TRUST_FAIL
            signature_reasons = [
                "Trust @ Wheels failed; no editorial score or human preference may override it."
            ]
        elif (
            trust.status == TrustWheelStatus.PASS
            and human_review is not None
            and human_review.verdict == EditorialVerdict.WOULD_PUBLISH_NOW
            and not high_losses
        ):
            signature = DynoSignature.SIGNED_PASS
            signature_reasons = [
                "Trust @ Wheels PASS and explicit human verdict WOULD_PUBLISH_NOW with no HIGH drivetrain losses."
            ]
        else:
            signature = DynoSignature.UNSIGNED
            signature_reasons = [
                "The product-output dyno is incomplete or the final asset is not yet publish-now quality."
            ]

        angle_family = None
        if run.angle_selection is not None:
            angle_family = run.angle_selection.selected_candidate.content_family.value

        visual_provider = run.visual_render.provider if run.visual_render else None
        visual_sha = run.visual_render.asset_sha256 if run.visual_render else None
        source_packet_id = (
            run.generation_source_packet.packet_id if run.generation_source_packet else None
        )

        return ContentDynoCaseReport(
            dyno_version=cls.VERSION,
            run_id=run.run_id,
            topic=run.topic,
            style=run.style,
            final_content_sha256=cls._sha256(run.final_content),
            generation_source_packet_id=source_packet_id,
            content_profile_id=run.content_profile_id,
            angle_family=angle_family,
            final_status=run.final_status,
            visual_provider=visual_provider,
            visual_asset_sha256=visual_sha,
            editorial_sensors=cls._editorial_sensors(run),
            trust_at_wheels=trust,
            drivetrain_losses=losses,
            human_review=human_review,
            signature=signature,
            signature_reasons=signature_reasons,
        )

    @classmethod
    def batch(cls, reports: list[ContentDynoCaseReport]) -> ContentDynoBatchReport:
        if not reports:
            raise ValueError("CONTENT-DYNO requires at least one case report")
        signed = sum(report.signature == DynoSignature.SIGNED_PASS for report in reports)
        trust_fail = sum(report.signature == DynoSignature.TRUST_FAIL for report in reports)
        unsigned = len(reports) - signed - trust_fail
        would_publish = sum(
            report.human_review is not None
            and report.human_review.verdict == EditorialVerdict.WOULD_PUBLISH_NOW
            for report in reports
        )
        loss_frequency = Counter(
            loss.code for report in reports for loss in report.drivetrain_losses
        )
        return ContentDynoBatchReport(
            dyno_version=cls.VERSION,
            case_count=len(reports),
            signed_pass_count=signed,
            trust_fail_count=trust_fail,
            unsigned_count=unsigned,
            would_publish_now_count=would_publish,
            would_publish_now_rate=would_publish / len(reports),
            loss_frequency=dict(sorted(loss_frequency.items())),
            reports=reports,
        )
