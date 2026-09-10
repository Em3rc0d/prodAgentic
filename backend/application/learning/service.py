from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

from domain.learning.models import (
    PERFORMANCE_POLICY_VERSION,
    ConfidenceBand,
    PerformanceDimension,
    PerformanceEvidenceSetV1,
    PerformanceObservationV1,
    PerformanceSignalV1,
    PerformanceSummaryV1,
    PlannerPerformanceScoreV1,
    canonical_sha256,
    confidence_for_sample,
    deterministic_signal_id,
    deterministic_summary_id,
    planner_weight_for_confidence,
)


class PerformanceLearningUnavailable(RuntimeError):
    pass


def _utc_millis(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _percentile(values: list[float], current: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 0.5
    below = sum(1 for value in values if value < current)
    equal = sum(1 for value in values if value == current)
    rank = (below + 0.5 * equal) / len(values)
    return round(max(0.0, min(1.0, rank)), 6)


def _observation_score(
    observation: PerformanceObservationV1,
    *,
    interaction_rates: list[float],
    impressions: list[float],
) -> float:
    interaction_rate = (
        observation.reactions + observation.comments + observation.shares
    ) / observation.impressions
    interaction_percentile = _percentile(interaction_rates, interaction_rate)
    impression_percentile = _percentile(impressions, float(observation.impressions))
    return round(0.70 * interaction_percentile + 0.30 * impression_percentile, 6)


def _dimension_key(observation: PerformanceObservationV1, dimension: PerformanceDimension) -> str | None:
    mapping = {
        PerformanceDimension.ROLE: observation.role,
        PerformanceDimension.CANONICAL_TOPIC: observation.canonical_topic,
        PerformanceDimension.FORMAT: observation.format,
        PerformanceDimension.HOOK_PATTERN: observation.hook_pattern,
        PerformanceDimension.VISUAL_PATTERN: observation.visual_pattern,
        PerformanceDimension.PLATFORM: observation.provider,
    }
    value = mapping[dimension]
    return value if value else None


class PerformanceSummaryService:
    def __init__(self, *, evidence, summaries):
        self.evidence = evidence
        self.summaries = summaries

    async def rebuild(
        self,
        profile_id: str,
        *,
        now: datetime | None = None,
    ) -> PerformanceSummaryV1:
        evidence: PerformanceEvidenceSetV1 = await self.evidence.list_for_profile(profile_id)
        ordered = tuple(
            sorted(
                evidence.observations,
                key=lambda item: (item.captured_at, item.publication_id, item.metric_snapshot_id),
            )
        )
        input_payload = {
            "policy_version": PERFORMANCE_POLICY_VERSION,
            "tenant_id": evidence.tenant_id,
            "profile_id": evidence.profile_id,
            "observations": [item.model_dump(mode="python") for item in ordered],
        }
        input_digest = canonical_sha256(input_payload)
        existing = await self.summaries.get_by_input_digest(profile_id, input_digest)
        if existing is not None:
            return existing

        created_at = _utc_millis(now or datetime.now(timezone.utc))
        limitations = [
            "Observational association only; S12 does not claim causality.",
            "Only mature t+72h/t+7d lifecycle snapshots are eligible for planner learning.",
            "Learning requires impressions plus reactions, comments and shares; unavailable metrics are never zero-filled.",
        ]
        if evidence.excluded_incomplete_count:
            limitations.append(
                f"Excluded {evidence.excluded_incomplete_count} mature snapshot(s) with incomplete normalized metrics."
            )
        if evidence.excluded_unattributed_count:
            limitations.append(
                f"Excluded {evidence.excluded_unattributed_count} snapshot(s) without a complete tenant-scoped publication/content attribution chain."
            )

        if not ordered:
            input_summary = {
                "schema_version": 1,
                "summary_id": deterministic_summary_id(
                    tenant_id=evidence.tenant_id,
                    profile_id=profile_id,
                    input_digest=input_digest,
                ),
                "tenant_id": evidence.tenant_id,
                "profile_id": profile_id,
                "policy_version": PERFORMANCE_POLICY_VERSION,
                "window_start": None,
                "window_end": None,
                "sample_size": 0,
                "eligible_publication_ids": (),
                "input_snapshot_ids": (),
                "input_digest": input_digest,
                "baseline_score": None,
                "signals": (),
                "insufficient_dimensions": tuple(PerformanceDimension),
                "latest_snapshot_at": None,
                "limitations": tuple(limitations + ["Insufficient mature evidence; planner performance contribution is zero."]),
                "created_at": created_at,
            }
            digest_payload = {key: value for key, value in input_summary.items() if key != "created_at"}
            summary = PerformanceSummaryV1(
                **input_summary,
                summary_digest=canonical_sha256(digest_payload),
            )
            return await self.summaries.append(summary)

        interaction_rates = [
            (item.reactions + item.comments + item.shares) / item.impressions
            for item in ordered
        ]
        impression_values = [float(item.impressions) for item in ordered]
        scores = {
            item.publication_id: _observation_score(
                item,
                interaction_rates=interaction_rates,
                impressions=impression_values,
            )
            for item in ordered
        }
        baseline = round(mean(scores.values()), 6)

        signals: list[PerformanceSignalV1] = []
        influential_dimensions: set[PerformanceDimension] = set()
        for dimension in PerformanceDimension:
            groups: dict[str, list[PerformanceObservationV1]] = defaultdict(list)
            for observation in ordered:
                key = _dimension_key(observation, dimension)
                if key is not None:
                    groups[key].append(observation)
            for key in sorted(groups):
                members = groups[key]
                group_score = round(mean(scores[item.publication_id] for item in members), 6)
                lift = round(max(-1.0, min(1.0, group_score - baseline)), 6)
                confidence = confidence_for_sample(len(members))
                planner_weight = planner_weight_for_confidence(confidence)
                if planner_weight > 0:
                    influential_dimensions.add(dimension)
                signals.append(
                    PerformanceSignalV1(
                        signal_id=deterministic_signal_id(
                            profile_id=profile_id,
                            input_digest=input_digest,
                            dimension=dimension.value,
                            key=key,
                        ),
                        dimension=dimension,
                        key=key,
                        sample_size=len(members),
                        mean_observation_score=group_score,
                        baseline_score=baseline,
                        lift=lift,
                        confidence=confidence,
                        planner_weight=planner_weight,
                        note=(
                            "Descriptive association versus this profile baseline; "
                            "performance remains subordinate to Brand/Safety/Novelty/Diversity/Quality."
                        ),
                    )
                )

        if len(ordered) < 5:
            limitations.append(
                "Profile sample is below five mature publications; all current learning signals are explanatory only."
            )
        insufficient = tuple(
            dimension for dimension in PerformanceDimension if dimension not in influential_dimensions
        )
        window_start = min(item.captured_at for item in ordered)
        window_end = max(item.captured_at for item in ordered)
        input_summary = {
            "schema_version": 1,
            "summary_id": deterministic_summary_id(
                tenant_id=evidence.tenant_id,
                profile_id=profile_id,
                input_digest=input_digest,
            ),
            "tenant_id": evidence.tenant_id,
            "profile_id": profile_id,
            "policy_version": PERFORMANCE_POLICY_VERSION,
            "window_start": window_start,
            "window_end": window_end,
            "sample_size": len(ordered),
            "eligible_publication_ids": tuple(item.publication_id for item in ordered),
            "input_snapshot_ids": tuple(item.metric_snapshot_id for item in ordered),
            "input_digest": input_digest,
            "baseline_score": baseline,
            "signals": tuple(signals),
            "insufficient_dimensions": insufficient,
            "latest_snapshot_at": window_end,
            "limitations": tuple(limitations),
            "created_at": created_at,
        }
        digest_payload = {key: value for key, value in input_summary.items() if key != "created_at"}
        summary = PerformanceSummaryV1(
            **input_summary,
            summary_digest=canonical_sha256(digest_payload),
        )
        return await self.summaries.append(summary)


class PlannerPerformanceSource:
    def __init__(self, service: PerformanceSummaryService):
        self.service = service

    async def get_for_planning(self, profile_id: str) -> PerformanceSummaryV1 | None:
        try:
            return await self.service.rebuild(profile_id)
        except LookupError:
            raise
        except Exception as exc:
            raise PerformanceLearningUnavailable(
                "Performance summary is temporarily unavailable; planning may proceed without learning"
            ) from exc

    def score_candidate(
        self,
        summary: PerformanceSummaryV1,
        *,
        role: str,
        canonical_topic: str,
        format: str,
        hook_pattern: str,
        visual_pattern: str | None,
    ) -> PlannerPerformanceScoreV1:
        candidate_keys = {
            PerformanceDimension.ROLE: role,
            PerformanceDimension.CANONICAL_TOPIC: canonical_topic,
            PerformanceDimension.FORMAT: format,
            PerformanceDimension.HOOK_PATTERN: hook_pattern,
            PerformanceDimension.VISUAL_PATTERN: visual_pattern,
        }
        contributions: list[tuple[float, float, str]] = []
        for signal in summary.signals:
            expected = candidate_keys.get(signal.dimension)
            if expected is None or signal.key != expected or signal.planner_weight <= 0:
                continue
            contributions.append((signal.lift, signal.planner_weight, signal.signal_id))
        if not contributions:
            return PlannerPerformanceScoreV1(
                score=0.0,
                matched_signal_ids=(),
                note="No medium/high-confidence matching performance signal; tie-breaker contribution is zero.",
            )
        weighted = sum(lift * weight for lift, weight, _ in contributions)
        total_weight = sum(weight for _, weight, _ in contributions)
        score = round(max(-1.0, min(1.0, weighted / total_weight)), 6)
        return PlannerPerformanceScoreV1(
            score=score,
            matched_signal_ids=tuple(signal_id for _, _, signal_id in contributions),
            note=(
                "Bounded observational tie-breaker only; stronger planner constraints have already been satisfied."
            ),
        )
