from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from application.planning.strict import (
    BatchCompletenessConflict,
    BatchDistinctnessConflict,
    R4StrictBatchPlannerService,
    batch_distinctness_issues,
)
from domain.planning.models import BatchRequestConstraints, ContentItem, IdeaCandidateV1, TargetWindow
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

NOW = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)


def _authority():
    provisional = ProfileVersion(
        profile_id="profile-r4",
        tenant_id="tenant-r4",
        version=2,
        identity=ProfileIdentity(name="EM3RC0D", account_type="education", summary="Systems engineering education"),
        goals=("educate", "build_authority"),
        audience=("systems engineering students",),
        editorial_strategy=EditorialStrategy(topic_families=("sql", "cloud", "architecture", "networks")),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("direct",), target_language="es"),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "bold")),
        publishing_preferences=PublishingPreferences(channels=("linkedin", "manual_export"), default_batch_size=4),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id=version.profile_id,
        tenant_id=version.tenant_id,
        current_version=version.version,
        name=version.identity.name,
        status=ProfileStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    return profile, version


class Profiles:
    def __init__(self):
        self.profile, self.version = _authority()

    async def get_profile(self, profile_id):
        return self.profile if profile_id == self.profile.profile_id else None

    async def get_version(self, profile_id, version):
        if profile_id == self.profile.profile_id and version == self.version.version:
            return self.version
        return None


class Repository:
    def __init__(self):
        self.saved = None

    async def list_recent_memory(self, profile_id, since):
        return []

    async def save_batch(self, batch, items, plans, trace):
        assert self.saved is None
        self.saved = (batch, tuple(items), tuple(plans), trace)


class Projector:
    async def refresh(self, profile_id, now):
        return 0


class Source:
    def __init__(self, candidates):
        self.candidates = candidates

    def generate(self, profile, target_window, constraints, target_pool_size):
        return list(self.candidates)[:target_pool_size]


def _candidate(index, topic, angle, *, role="education", hook="question", fmt="carousel"):
    return IdeaCandidateV1(
        candidate_id=f"candidate-{index}",
        role=role,
        topic=topic,
        subtopics=(),
        angle=angle,
        hook_pattern=hook,
        target_effect="understanding",
        tentative_format=fmt,
        rationale=f"distinct governed concept {index}",
        claim_risk="low",
    )


def _window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


@pytest.mark.asyncio
async def test_r4_exact_four_is_persisted_only_after_completeness_and_distinctness_pass():
    repository = Repository()
    candidates = [
        _candidate(1, "sql indexes", "why indexes change query cost", role="education", hook="question"),
        _candidate(2, "cloud queues", "backpressure during traffic spikes", role="insight", hook="counterintuitive", fmt="infographic"),
        _candidate(3, "software architecture", "failure ownership before diagrams", role="value", hook="diagram_flow", fmt="single_image"),
        _candidate(4, "computer networks", "latency budget worked example", role="relatable", hook="story", fmt="carousel"),
    ]
    service = R4StrictBatchPlannerService(Profiles(), repository, Source(candidates), Projector())

    result = await service.create_batch(
        "tenant-r4", "profile-r4", _window(), 4, BatchRequestConstraints(), now=NOW
    )

    assert result.batch.selected_size == 4
    assert len(result.items) == 4
    assert repository.saved is not None
    assert not batch_distinctness_issues(result.items)


@pytest.mark.asyncio
async def test_r4_shortfall_fails_closed_and_never_persists_partial_batch():
    repository = Repository()
    candidates = [
        _candidate(1, "sql indexes", "query planner basics"),
        _candidate(2, "cloud queues", "backpressure basics", role="insight", hook="counterintuitive"),
        _candidate(3, "software architecture", "failure ownership", role="value", hook="diagram_flow"),
    ]
    service = R4StrictBatchPlannerService(Profiles(), repository, Source(candidates), Projector())

    with pytest.raises(BatchCompletenessConflict, match="selected 3 of 4"):
        await service.create_batch(
            "tenant-r4", "profile-r4", _window(), 4, BatchRequestConstraints(), now=NOW
        )

    assert repository.saved is None


def test_distinctness_policy_catches_cosmetic_single_concept_variants():
    def item(content_id, topic, angle):
        return ContentItem(
            content_id=content_id,
            tenant_id="tenant-r4",
            batch_id="batch-r4",
            profile_id="profile-r4",
            profile_version=2,
            canonical_topic=topic,
            angle=angle,
            role="education",
            target_effect="understanding",
            format="carousel",
            hook_pattern="question",
            created_at=NOW,
            updated_at=NOW,
        )

    issues = batch_distinctness_issues([
        item("one", "sql.tips", "quick tips"),
        item("two", "sql.mistakes", "common mistakes"),
    ])
    assert issues
    assert issues[0].similarity == 1.0


@pytest.mark.asyncio
async def test_r4_distinctness_failure_never_commits_staged_batch():
    repository = Repository()
    candidates = [
        _candidate(1, "sql tips", "quick tips", role="education", hook="question"),
        _candidate(2, "sql mistakes", "common mistakes", role="insight", hook="story"),
        _candidate(3, "cloud queues", "backpressure", role="value", hook="counterintuitive"),
        _candidate(4, "computer networks", "latency", role="relatable", hook="diagram_flow"),
    ]
    service = R4StrictBatchPlannerService(Profiles(), repository, Source(candidates), Projector())

    with pytest.raises((BatchCompletenessConflict, BatchDistinctnessConflict)):
        await service.create_batch(
            "tenant-r4", "profile-r4", _window(), 4, BatchRequestConstraints(), now=NOW
        )

    assert repository.saved is None
