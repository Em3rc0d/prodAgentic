from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from application.planning import BatchPlannerService, DeterministicCandidateSource, NoveltyEngine
from domain.planning.models import (
    BatchRequestConstraints,
    EditorialMemoryEntry,
    IdeaCandidateV1,
    LifecycleSource,
    NoveltyVerdict,
    TargetWindow,
    canonicalize_topic,
    semantic_fingerprint,
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


NOW = datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc)


def make_profile(*, profile_id="p1", topics=("systems", "databases", "apis", "caching"), goals=("educate", "build_authority")):
    payload = {
        "schema_version": 2,
        "profile_id": profile_id,
        "tenant_id": "tenant-a",
        "version": 3,
        "identity": ProfileIdentity(name="Golden Profile", account_type="education", summary="Golden profile"),
        "goals": goals,
        "audience": ("builders and practitioners",),
        "editorial_strategy": EditorialStrategy(topic_families=topics),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(voice_traits=("direct",), target_language="es"),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(),
        "publishing_preferences": PublishingPreferences(channels=("manual_export",), default_batch_size=4),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW - timedelta(days=10),
        "created_at": NOW - timedelta(days=10),
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id=profile_id,
        tenant_id="tenant-a",
        current_version=version.version,
        name=version.identity.name,
        status=ProfileStatus.ACTIVE,
        created_at=NOW - timedelta(days=10),
        updated_at=NOW - timedelta(days=10),
    )
    return profile, version


def candidate(candidate_id, role, topic, angle, hook, fmt="text", rationale=None):
    return IdeaCandidateV1(
        candidate_id=candidate_id,
        role=role,
        topic=topic,
        angle=angle,
        hook_pattern=hook,
        target_effect="useful outcome",
        tentative_format=fmt,
        rationale=rationale or f"{role} / {angle}",
        claim_risk="low",
    )


def memory(memory_id, topic, angle, *, days=1, hook="question", source=LifecycleSource.PUBLISHED, role="education", fmt="text"):
    canonical = canonicalize_topic(topic)
    return EditorialMemoryEntry(
        memory_id=memory_id,
        tenant_id="tenant-a",
        profile_id="p1",
        content_id=f"content-{memory_id}",
        revision_id=f"revision-{memory_id}",
        lifecycle_source=source,
        canonical_topic=canonical,
        angle=angle,
        hook_pattern=hook,
        role=role,
        format=fmt,
        semantic_fingerprint=semantic_fingerprint(canonical, angle),
        effective_at=NOW - timedelta(days=days),
        weight=0.6 if source == LifecycleSource.READY_FOR_REVIEW else 1.0,
        created_at=NOW,
    )


class FakeProfileRepository:
    def __init__(self, profile, version):
        self.profile = profile
        self.version = version

    async def get_profile(self, profile_id):
        return self.profile if profile_id == self.profile.profile_id else None

    async def get_version(self, profile_id, version):
        if profile_id == self.profile.profile_id and version == self.version.version:
            return self.version
        return None


class MemoryPlanningRepository:
    def __init__(self, entries=None):
        self.memory = list(entries or [])
        self.saved = None

    async def list_recent_memory(self, profile_id, since):
        return [item for item in self.memory if item.profile_id == profile_id and item.effective_at >= since]

    async def replace_projected_memory(self, profile_id, entries, source_prefix):
        return None

    async def save_batch(self, batch, items, plans, trace):
        self.saved = (batch, list(items), list(plans), trace)

    async def get_batch(self, batch_id):
        return self.saved[0] if self.saved and self.saved[0].batch_id == batch_id else None

    async def list_batch_items(self, batch_id):
        return self.saved[1] if self.saved and self.saved[0].batch_id == batch_id else []

    async def list_batch_plans(self, batch_id):
        return self.saved[2] if self.saved and self.saved[0].batch_id == batch_id else []

    async def get_planning_trace(self, batch_id):
        return self.saved[3] if self.saved and self.saved[0].batch_id == batch_id else None


class NoopProjector:
    async def refresh(self, profile_id, now):
        return 0


class FixtureSource:
    def __init__(self, candidates):
        self.candidates = list(candidates)
        self.requested_pool_size = None

    def generate(self, profile, target_window, constraints, target_pool_size):
        self.requested_pool_size = target_pool_size
        return list(self.candidates)[:target_pool_size]


def window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


def test_deterministic_source_builds_oversized_bounded_pool():
    _, version = make_profile()
    source = DeterministicCandidateSource()
    generated = source.generate(version, window(), BatchRequestConstraints(), 12)
    assert len(generated) == 12
    assert len({item.candidate_id for item in generated}) == 12
    assert len(generated) > 4


def test_novelty_cooldown_layers_are_explicit_and_explainable():
    engine = NoveltyEngine()
    item = candidate("c1", "education", "llantas", "how it works", "question")

    hard = engine.evaluate(item, [memory("m1", "neumáticos", "maintenance", days=1)], [], NOW)
    assert hard.verdict == NoveltyVerdict.BLOCKED
    assert hard.cooldown_band.value == "HARD_COOLDOWN"
    assert "canonical_topic" in hard.overlap_categories
    assert hard.matched_content_ids == ("content-m1",)

    strong = engine.evaluate(item, [memory("m2", "tires", "different angle", days=4)], [], NOW)
    assert strong.verdict == NoveltyVerdict.REPLACE_TOPIC
    assert strong.cooldown_band.value == "STRONG_COOLDOWN"

    older_same_angle = engine.evaluate(item, [memory("m3", "tyres", "how it works", days=10)], [], NOW)
    assert older_same_angle.verdict == NoveltyVerdict.REWRITE_ANGLE

    older_fresh_angle = engine.evaluate(item, [memory("m4", "tires", "buying guide", days=10)], [], NOW)
    assert older_fresh_angle.verdict == NoveltyVerdict.PASS_WITH_WARNING


def test_ready_for_review_is_soft_memory_not_published_authority():
    engine = NoveltyEngine()
    item = candidate("c1", "education", "sql", "practical checklist", "numbered")
    result = engine.evaluate(
        item,
        [memory("soft", "sql", "practical checklist", days=1, source=LifecycleSource.READY_FOR_REVIEW)],
        [],
        NOW,
    )
    assert result.verdict == NoveltyVerdict.REWRITE_ANGLE


def test_current_batch_duplicate_is_caught_without_persisting_fake_memory():
    engine = NoveltyEngine()
    first = candidate("a", "education", "caching", "how it works", "question", "carousel")
    duplicate = candidate("b", "education", "caching", "how it works", "question", "carousel")
    result = engine.evaluate(duplicate, [], [first], NOW)
    assert result.verdict == NoveltyVerdict.BLOCKED
    assert result.cooldown_band.value == "CURRENT_BATCH"
    assert any(match.lifecycle_source.startswith("CURRENT_BATCH:") for match in result.matches)


@pytest.mark.asyncio
async def test_planner_freezes_profile_version_and_returns_fewer_honestly():
    profile, version = make_profile(topics=("topic-a", "topic-b", "topic-c"))
    candidates = [
        candidate("blocked-a", "education", "topic-a", "how it works", "question"),
        candidate("blocked-b", "insight", "topic-b", "tradeoff", "counterintuitive"),
        candidate("fresh-c", "education", "topic-c", "worked example", "story", "carousel"),
    ]
    repository = MemoryPlanningRepository(
        [
            memory("ma", "topic-a", "different", days=1),
            memory("mb", "topic-b", "different", days=1),
        ]
    )
    source = FixtureSource(candidates)
    service = BatchPlannerService(
        FakeProfileRepository(profile, version), repository, source, NoopProjector()
    )
    result = await service.create_batch(
        "tenant-a", "p1", window(), 4, BatchRequestConstraints(), now=NOW
    )

    assert source.requested_pool_size == 12
    assert result.batch.requested_size == 4
    assert result.batch.selected_size == 1
    assert result.batch.state.value == "PARTIAL"
    assert "were not relaxed" in result.batch.shortfall_reason
    assert result.batch.profile_version == 3
    assert result.batch.profile_snapshot_digest == version.digest
    assert result.batch.strategy_snapshot.performance_summary_version is None
    assert all(item.profile_version == 3 for item in result.items)
    assert all(plan.plan.profile_version == 3 for plan in result.plans)
    assert repository.saved is not None


GOLDENS = {
    "content-seller": {
        "memory": [memory("cs-old", "career checklist", "three things students should do", days=1, hook="numbered")],
        "candidates": [
            candidate("cs-repeat", "education", "career checklist", "three things students should do", "numbered", "carousel"),
            candidate("cs-rel", "relatable", "remote work", "expectation vs reality", "story", "single_image"),
            candidate("cs-edu", "education", "portfolio evidence", "worked example", "diagram_flow", "carousel"),
            candidate("cs-personal", "personal_story", "first internship", "personal realization", "story", "text"),
            candidate("cs-community", "community", "learning habits", "question to peers", "question", "single_image"),
        ],
    },
    "logan": {
        "memory": [memory("logan-old", "llantas", "diagnosis", days=1, hook="question", role="symptom")],
        "candidates": [
            candidate("logan-repeat", "symptom", "tires", "diagnosis", "question", "single_image"),
            candidate("logan-safety", "safety", "brake fluid", "safety", "warning", "single_image"),
            candidate("logan-explain", "mechanical_explainer", "wheel bearing", "how it works", "diagram_flow", "infographic"),
            candidate("logan-maint", "maintenance", "air filter", "maintenance", "checklist", "carousel"),
            candidate("logan-symptom", "symptom", "steering alignment", "diagnosis", "question", "text"),
        ],
    },
    "tech": {
        "memory": [memory("tech-old", "sql", "checklist", days=1, hook="numbered")],
        "candidates": [
            candidate("tech-repeat", "technical_learning", "sql", "checklist", "numbered", "carousel"),
            candidate("tech-system", "system_design", "event queues", "tradeoff", "diagram_flow", "infographic"),
            candidate("tech-learn", "technical_learning", "cache invalidation", "how it works", "question", "carousel"),
            candidate("tech-humor", "humor", "merge conflicts", "recognizable moment", "story", "single_image"),
            candidate("tech-trade", "tradeoff", "api pagination", "comparison", "counterintuitive", "text"),
        ],
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", ["content-seller", "logan", "tech"])
async def test_golden_planning_fixtures_block_repetition_and_keep_diversity(fixture_name):
    profile, version = make_profile()
    fixture = GOLDENS[fixture_name]
    repository = MemoryPlanningRepository(fixture["memory"])
    service = BatchPlannerService(
        FakeProfileRepository(profile, version),
        repository,
        FixtureSource(fixture["candidates"]),
        NoopProjector(),
    )
    result = await service.create_batch(
        "tenant-a", "p1", window(), 4, BatchRequestConstraints(), now=NOW
    )

    assert result.batch.selected_size == 4
    selected_candidate_ids = {plan.plan.candidate_id for plan in result.plans}
    assert not any(value.endswith("repeat") or "repeat" in value for value in selected_candidate_ids)
    assert len({item.role for item in result.items}) >= 3
    assert len({item.hook_pattern for item in result.items}) >= 3
    assert len({item.format for item in result.items}) >= 3
    assert result.trace.digest
    blocked = [evaluation for evaluation in result.trace.evaluations if evaluation.novelty.verdict == NoveltyVerdict.BLOCKED]
    assert blocked
