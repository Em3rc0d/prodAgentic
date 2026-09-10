from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from application.learning import PerformanceLearningUnavailable, PerformanceSummaryService
from application.planning import BatchPlannerService
from domain.analytics.models import (
    ANALYTICS_SOURCE_VERSION,
    MetricSnapshotV1,
    NormalizedMetric,
    SnapshotFreshnessV1,
    analytics_operation_key,
    canonical_sha256 as analytics_sha256,
    deterministic_snapshot_id,
)
from domain.learning.models import (
    ConfidenceBand,
    PerformanceDimension,
    PerformanceEvidenceSetV1,
    PerformanceObservationV1,
    PerformanceSummaryV1,
    PlannerPerformanceScoreV1,
    canonical_sha256 as learning_sha256,
    confidence_for_sample,
    deterministic_summary_id,
)
from domain.planning.models import (
    BatchRequestConstraints,
    IdeaCandidateV1,
    NoveltyResultV1,
    NoveltyVerdict,
    TargetWindow,
    canonicalize_topic,
)
from domain.profiles.models import (
    AgentPolicy,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    MigrationProvenance,
    NoveltyPolicy,
    Profile,
    ProfileIdentity,
    ProfileStatus,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest,
)
from domain.tenants.models import TenantContext
from infrastructure.mongo.analytics import MongoMetricSnapshotRepository
from infrastructure.mongo.learning import (
    MongoPerformanceEvidenceRepository,
    MongoPerformanceSummaryRepository,
)


NOW = datetime(2026, 9, 10, 3, 0, tzinfo=timezone.utc)


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_s12_{uuid4().hex}"]
    return client, db


def _context(tenant: str = "tenant-a") -> TenantContext:
    return TenantContext(tenant_id=tenant, actor_id="s12-cert", actor_type="worker")


def _ms(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _observation(
    index: int,
    *,
    role: str = "education",
    topic: str = "tech.systems",
    fmt: str = "text",
    hook: str = "question",
    impressions: int = 100,
    reactions: int = 10,
    comments: int = 2,
    shares: int = 1,
) -> PerformanceObservationV1:
    return PerformanceObservationV1(
        tenant_id="tenant-a",
        profile_id="p1",
        publication_id=f"pub-{index}",
        metric_snapshot_id=f"metric-{index}",
        snapshot_digest=f"{index + 1:064x}"[-64:],
        captured_at=_ms(NOW + timedelta(minutes=index)),
        provider="linkedin",
        role=role,
        canonical_topic=topic,
        format=fmt,
        hook_pattern=hook,
        visual_pattern=None,
        impressions=impressions,
        reactions=reactions,
        comments=comments,
        shares=shares,
    )


class FakeEvidence:
    def __init__(self, observations):
        self.value = PerformanceEvidenceSetV1(
            tenant_id="tenant-a",
            profile_id="p1",
            candidate_snapshot_count=len(observations),
            excluded_incomplete_count=0,
            excluded_unattributed_count=0,
            observations=tuple(observations),
        )

    async def list_for_profile(self, profile_id):
        if profile_id != "p1":
            raise LookupError("Profile not found")
        return self.value


class MemorySummaries:
    def __init__(self):
        self.items: list[PerformanceSummaryV1] = []

    async def get_by_input_digest(self, profile_id, input_digest):
        return next(
            (
                item
                for item in self.items
                if item.profile_id == profile_id and item.input_digest == input_digest
            ),
            None,
        )

    async def append(self, summary):
        existing = await self.get_by_input_digest(summary.profile_id, summary.input_digest)
        if existing is not None:
            return existing
        self.items.append(summary)
        return summary

    async def latest_for_profile(self, profile_id):
        candidates = [item for item in self.items if item.profile_id == profile_id]
        return candidates[-1] if candidates else None


def test_confidence_policy_blocks_tiny_samples_from_planner_weight():
    assert confidence_for_sample(0) is ConfidenceBand.INSUFFICIENT
    assert confidence_for_sample(2) is ConfidenceBand.INSUFFICIENT
    assert confidence_for_sample(3) is ConfidenceBand.LOW
    assert confidence_for_sample(4) is ConfidenceBand.LOW
    assert confidence_for_sample(5) is ConfidenceBand.MEDIUM
    assert confidence_for_sample(9) is ConfidenceBand.MEDIUM
    assert confidence_for_sample(10) is ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_summary_is_deterministic_idempotent_and_low_sample_is_explanatory_only():
    repo = MemorySummaries()
    service = PerformanceSummaryService(
        evidence=FakeEvidence([_observation(0), _observation(1), _observation(2)]),
        summaries=repo,
    )
    first = await service.rebuild("p1", now=NOW)
    second = await service.rebuild("p1", now=NOW + timedelta(hours=1))
    assert first == second
    assert first.summary_id == deterministic_summary_id(
        tenant_id="tenant-a", profile_id="p1", input_digest=first.input_digest
    )
    assert len(repo.items) == 1
    assert first.sample_size == 3
    assert first.signals
    assert all(signal.confidence is ConfidenceBand.LOW for signal in first.signals)
    assert all(signal.planner_weight == 0 for signal in first.signals)
    assert "causality" in " ".join(first.limitations).lower()


@pytest.mark.asyncio
async def test_five_matching_observations_promote_medium_confidence_not_full_weight():
    repo = MemorySummaries()
    observations = [
        _observation(
            index,
            impressions=100 + index * 10,
            reactions=5 + index,
            comments=index % 2,
            shares=1,
        )
        for index in range(5)
    ]
    summary = await PerformanceSummaryService(
        evidence=FakeEvidence(observations), summaries=repo
    ).rebuild("p1", now=NOW)
    role = next(
        signal
        for signal in summary.signals
        if signal.dimension is PerformanceDimension.ROLE and signal.key == "education"
    )
    assert role.sample_size == 5
    assert role.confidence is ConfidenceBand.MEDIUM
    assert role.planner_weight == 0.5
    assert -1 <= role.lift <= 1


def _metric_snapshot(
    *,
    tenant: str,
    publication_id: str,
    bucket: str,
    captured_at: datetime,
    impressions: int,
    reactions: int = 5,
    comments: int = 2,
    shares: int | None = 1,
) -> MetricSnapshotV1:
    operation_key = analytics_operation_key(
        tenant_id=tenant,
        publication_id=publication_id,
        provider="linkedin",
        external_post_id=f"urn:li:share:{publication_id}",
        collection_bucket=bucket,
    )
    raw = {
        "IMPRESSION": impressions,
        "REACTION": reactions,
        "COMMENT": comments,
    }
    normalized = {
        NormalizedMetric.VIEWS_OR_IMPRESSIONS.value: impressions,
        NormalizedMetric.LIKES_OR_REACTIONS.value: reactions,
        NormalizedMetric.COMMENTS.value: comments,
    }
    unavailable = ["MEMBERS_REACHED"]
    if shares is None:
        unavailable.append("RESHARE")
    else:
        raw["RESHARE"] = shares
        normalized[NormalizedMetric.SHARES.value] = shares
    captured_at = _ms(captured_at)
    freshness = SnapshotFreshnessV1(observed_at=captured_at)
    payload = {
        "schema_version": 1,
        "metric_snapshot_id": deterministic_snapshot_id(operation_key),
        "operation_key": operation_key,
        "tenant_id": tenant,
        "publication_id": publication_id,
        "provider": "linkedin",
        "external_post_id": f"urn:li:share:{publication_id}",
        "captured_at": captured_at,
        "raw_available_metrics": raw,
        "normalized_metrics": normalized,
        "unavailable_metrics": tuple(unavailable),
        "freshness": freshness.model_dump(mode="python"),
        "source_version": ANALYTICS_SOURCE_VERSION,
        "provider_api_version": "202608",
        "collection_bucket": bucket,
        "raw_digest": analytics_sha256(raw),
        "created_at": captured_at,
    }
    return MetricSnapshotV1(**payload, snapshot_digest=analytics_sha256(payload))


async def _insert_attribution(db, *, tenant: str, suffix: str, profile_id: str = "p1"):
    content_id = f"content-{suffix}"
    approval_id = f"approval-{suffix}"
    publication_id = f"pub-{suffix}"
    await db["content_items"].insert_one(
        {
            "tenant_id": tenant,
            "profile_id": profile_id,
            "content_id": content_id,
            "role": "education",
            "canonical_topic": f"tech.topic-{suffix}",
            "format": "text",
            "hook_pattern": "question",
            "visual_pattern": None,
        }
    )
    await db["approval_bundles"].insert_one(
        {"tenant_id": tenant, "approval_id": approval_id, "content_id": content_id}
    )
    await db["publications_v2"].insert_one(
        {
            "tenant_id": tenant,
            "publication_id": publication_id,
            "approval_id": approval_id,
            "provider": "linkedin",
            "state": "PUBLISHED",
        }
    )
    return publication_id


@pytest.mark.asyncio
async def test_mongo_evidence_prefers_t7d_excludes_incomplete_and_is_tenant_scoped():
    client, db = await _mongo()
    try:
        await db["profiles"].insert_many(
            [
                {"tenant_id": "tenant-a", "profile_id": "p1"},
                {"tenant_id": "tenant-b", "profile_id": "p1"},
            ]
        )
        pub_a = await _insert_attribution(db, tenant="tenant-a", suffix="a")
        pub_incomplete = await _insert_attribution(db, tenant="tenant-a", suffix="incomplete")
        pub_b = await _insert_attribution(db, tenant="tenant-b", suffix="b")

        repo_a = MongoMetricSnapshotRepository(db, _context("tenant-a"))
        repo_b = MongoMetricSnapshotRepository(db, _context("tenant-b"))
        await repo_a.append(
            _metric_snapshot(
                tenant="tenant-a",
                publication_id=pub_a,
                bucket="t+72h",
                captured_at=NOW,
                impressions=100,
            )
        )
        preferred = _metric_snapshot(
            tenant="tenant-a",
            publication_id=pub_a,
            bucket="t+7d",
            captured_at=NOW + timedelta(days=4),
            impressions=900,
        )
        await repo_a.append(preferred)
        await repo_a.append(
            _metric_snapshot(
                tenant="tenant-a",
                publication_id=pub_incomplete,
                bucket="t+7d",
                captured_at=NOW + timedelta(days=4),
                impressions=200,
                shares=None,
            )
        )
        await repo_b.append(
            _metric_snapshot(
                tenant="tenant-b",
                publication_id=pub_b,
                bucket="t+7d",
                captured_at=NOW + timedelta(days=4),
                impressions=5000,
            )
        )

        evidence = await MongoPerformanceEvidenceRepository(db, _context("tenant-a")).list_for_profile("p1")
        assert evidence.candidate_snapshot_count == 2
        assert len(evidence.observations) == 1
        assert evidence.observations[0].publication_id == pub_a
        assert evidence.observations[0].metric_snapshot_id == preferred.metric_snapshot_id
        assert evidence.observations[0].impressions == 900
        assert evidence.excluded_incomplete_count == 1
        assert all(item.tenant_id == "tenant-a" for item in evidence.observations)
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_mongo_summary_is_append_only_idempotent_and_cross_tenant_hidden():
    client, db = await _mongo()
    try:
        evidence = FakeEvidence([_observation(index) for index in range(5)]).value

        class FixedEvidence:
            async def list_for_profile(self, profile_id):
                return evidence

        repo = MongoPerformanceSummaryRepository(db, _context("tenant-a"))
        service = PerformanceSummaryService(evidence=FixedEvidence(), summaries=repo)
        first = await service.rebuild("p1", now=NOW)
        second = await service.rebuild("p1", now=NOW + timedelta(days=1))
        assert first == second
        assert await repo.collection.count_documents({"tenant_id": "tenant-a"}) == 1
        other = MongoPerformanceSummaryRepository(db, _context("tenant-b"))
        assert await other.latest_for_profile("p1") is None
    finally:
        await client.drop_database(db.name)
        client.close()


def _profile():
    payload = {
        "schema_version": 2,
        "profile_id": "p1",
        "tenant_id": "tenant-a",
        "version": 1,
        "identity": ProfileIdentity(name="S12 Profile", account_type="education", summary="S12 profile"),
        "goals": ("educate",),
        "audience": ("builders",),
        "editorial_strategy": EditorialStrategy(topic_families=("alpha", "beta", "gamma")),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(voice_traits=("direct",), target_language="es"),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(),
        "publishing_preferences": PublishingPreferences(channels=("manual_export",), default_batch_size=2),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW - timedelta(days=30),
        "created_at": NOW - timedelta(days=30),
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id="p1",
        tenant_id="tenant-a",
        current_version=1,
        name="S12 Profile",
        status=ProfileStatus.ACTIVE,
        created_at=NOW - timedelta(days=30),
        updated_at=NOW - timedelta(days=30),
    )
    return profile, version


class ProfileRepo:
    def __init__(self):
        self.profile, self.version = _profile()

    async def get_profile(self, profile_id):
        return self.profile if profile_id == "p1" else None

    async def get_version(self, profile_id, version):
        return self.version if profile_id == "p1" and version == 1 else None


class PlanningRepo:
    def __init__(self):
        self.saved = None

    async def list_recent_memory(self, profile_id, since):
        return []

    async def save_batch(self, batch, items, plans, trace):
        self.saved = (batch, items, plans, trace)


class NoopProjector:
    async def refresh(self, profile_id, now):
        return 0


class CandidateSource:
    def __init__(self, candidates):
        self.candidates = candidates

    def generate(self, profile, target_window, constraints, target_pool_size):
        return list(self.candidates)


def _candidate(candidate_id: str, *, role: str, topic: str, hook: str, fmt: str = "text"):
    return IdeaCandidateV1(
        candidate_id=candidate_id,
        role=role,
        topic=topic,
        angle=f"angle-{candidate_id}",
        hook_pattern=hook,
        target_effect="useful outcome",
        tentative_format=fmt,
        rationale=f"candidate {candidate_id}",
        claim_risk="low",
    )


class VerdictNovelty:
    def __init__(self, verdicts=None):
        self.verdicts = verdicts or {}

    def evaluate(self, candidate, memory, selected, now):
        verdict = self.verdicts.get(candidate.candidate_id, NoveltyVerdict.PASS)
        return NoveltyResultV1(
            novelty_result_id=f"nov-{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            verdict=verdict,
            canonical_topic=canonicalize_topic(candidate.topic),
            reasons=("fixture stronger gate",) if verdict is not NoveltyVerdict.PASS else (),
        )


def _empty_summary() -> PerformanceSummaryV1:
    input_digest = learning_sha256({"fixture": "s12"})
    summary_id = deterministic_summary_id(
        tenant_id="tenant-a", profile_id="p1", input_digest=input_digest
    )
    payload = {
        "schema_version": 1,
        "summary_id": summary_id,
        "tenant_id": "tenant-a",
        "profile_id": "p1",
        "policy_version": "s12-performance-v1",
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
        "limitations": ("fixture; observational association only",),
        "created_at": NOW,
    }
    digest_payload = {key: value for key, value in payload.items() if key != "created_at"}
    return PerformanceSummaryV1(**payload, summary_digest=learning_sha256(digest_payload))


class StaticPerformanceSource:
    def __init__(self, scores):
        self.summary = _empty_summary()
        self.scores = scores

    async def get_for_planning(self, profile_id):
        return self.summary

    def score_candidate(self, summary, **candidate):
        score = self.scores.get(candidate["canonical_topic"], 0.0)
        return PlannerPerformanceScoreV1(
            score=score,
            matched_signal_ids=(f"sig-{candidate['canonical_topic']}",) if score else (),
            note="bounded fixture tie-breaker",
        )


class DegradedPerformanceSource:
    async def get_for_planning(self, profile_id):
        raise PerformanceLearningUnavailable("fixture learning repository unavailable")

    def score_candidate(self, summary, **candidate):
        raise AssertionError("degraded source must not score candidates")


def _window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


async def _plan(candidates, *, requested=1, performance_source=None, verdicts=None):
    repo = PlanningRepo()
    service = BatchPlannerService(
        ProfileRepo(),
        repo,
        CandidateSource(candidates),
        NoopProjector(),
        novelty_engine=VerdictNovelty(verdicts),
        performance_source=performance_source,
    )
    result = await service.create_batch(
        "tenant-a", "p1", _window(), requested, BatchRequestConstraints(), now=NOW
    )
    return result


@pytest.mark.asyncio
async def test_learning_off_preserves_stable_s2_tie_order():
    first = _candidate("first", role="education", topic="alpha", hook="question")
    second = _candidate("second", role="education", topic="beta", hook="question")
    result = await _plan([first, second], performance_source=None)
    assert result.trace.evaluations[0].selected is True
    assert result.items[0].canonical_topic == canonicalize_topic("alpha")
    assert result.batch.strategy_snapshot.performance_summary_version is None


@pytest.mark.asyncio
async def test_hard_novelty_gate_cannot_be_overridden_by_high_performance():
    blocked = _candidate("blocked", role="education", topic="alpha", hook="question")
    safe = _candidate("safe", role="education", topic="beta", hook="question")
    source = StaticPerformanceSource(
        {canonicalize_topic("alpha"): 1.0, canonicalize_topic("beta"): -1.0}
    )
    result = await _plan(
        [blocked, safe],
        performance_source=source,
        verdicts={"blocked": NoveltyVerdict.BLOCKED},
    )
    assert result.items[0].canonical_topic == canonicalize_topic("beta")
    blocked_trace = next(item for item in result.trace.evaluations if item.candidate.candidate_id == "blocked")
    assert blocked_trace.performance_score == 0
    assert "stronger novelty gate" in blocked_trace.performance_note


@pytest.mark.asyncio
async def test_diversity_tuple_outranks_performance():
    duplicate_a = _candidate("a", role="education", topic="alpha", hook="question")
    duplicate_b = _candidate("b", role="education", topic="alpha", hook="question")
    diverse = _candidate("c", role="insight", topic="gamma", hook="counterintuitive", fmt="carousel")
    source = StaticPerformanceSource(
        {
            canonicalize_topic("alpha"): 1.0,
            canonicalize_topic("gamma"): -1.0,
        }
    )
    result = await _plan([duplicate_a, duplicate_b, diverse], requested=2, performance_source=source)
    selected_ids = {
        evaluation.candidate.candidate_id
        for evaluation in result.trace.evaluations
        if evaluation.selected
    }
    assert "c" in selected_ids
    assert not ({"a", "b"} <= selected_ids)


@pytest.mark.asyncio
async def test_performance_resolves_only_otherwise_equal_eligible_tie_and_binds_strategy():
    lower = _candidate("low", role="education", topic="alpha", hook="question")
    higher = _candidate("high", role="education", topic="beta", hook="question")
    source = StaticPerformanceSource(
        {canonicalize_topic("alpha"): -0.2, canonicalize_topic("beta"): 0.6}
    )
    result = await _plan([lower, higher], performance_source=source)
    assert result.items[0].canonical_topic == canonicalize_topic("beta")
    strategy = result.batch.strategy_snapshot
    assert strategy.performance_summary_version == "s12-performance-v1"
    assert strategy.performance_summary_id == source.summary.summary_id
    assert strategy.performance_summary_digest == source.summary.summary_digest
    trace = next(item for item in result.trace.evaluations if item.selected)
    assert trace.performance_score == 0.6
    serialized = str(result.trace.model_dump(mode="json")).lower()
    assert "raw_available_metrics" not in serialized
    assert "external_post_id" not in serialized


@pytest.mark.asyncio
async def test_learning_failure_degrades_to_zero_without_breaking_planning():
    first = _candidate("first", role="education", topic="alpha", hook="question")
    second = _candidate("second", role="education", topic="beta", hook="question")
    result = await _plan([first, second], performance_source=DegradedPerformanceSource())
    assert result.items
    assert result.batch.strategy_snapshot.performance_summary_id is None
    assert all(item.performance_score == 0 for item in result.trace.evaluations)
    assert any("unavailable" in (item.performance_note or "") for item in result.trace.evaluations)
