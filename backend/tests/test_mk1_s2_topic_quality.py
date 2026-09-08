from datetime import datetime, timedelta, timezone

import pytest

from application.planning import BatchPlannerService, DeterministicCandidateSource
from domain.planning.models import BatchRequestConstraints, TargetWindow
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

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
AUDIENCE = "drivers who wants to know how to get safe their cars"


def profile_without_topics():
    payload = {
        "schema_version": 2,
        "profile_id": "logan",
        "tenant_id": "tenant-a",
        "version": 1,
        "identity": ProfileIdentity(name="Logan Identity", account_type="personal_brand", summary=AUDIENCE),
        "goals": ("educate", "build_authority"),
        "audience": (AUDIENCE,),
        "editorial_strategy": EditorialStrategy(topic_families=()),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(voice_traits=("direct",), target_language="es"),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(),
        "publishing_preferences": PublishingPreferences(channels=("manual_export",), default_batch_size=4),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW,
        "created_at": NOW,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id="logan",
        tenant_id="tenant-a",
        current_version=1,
        name="Logan Identity",
        status=ProfileStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    return profile, version


def window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


class ProfileRepo:
    def __init__(self, profile, version):
        self.profile = profile
        self.version = version

    async def get_profile(self, profile_id):
        return self.profile if profile_id == self.profile.profile_id else None

    async def get_version(self, profile_id, version):
        return self.version if profile_id == self.profile.profile_id and version == self.version.version else None


class PlanningRepo:
    def __init__(self):
        self.saved = None

    async def list_recent_memory(self, profile_id, since):
        return []

    async def save_batch(self, batch, items, plans, trace):
        self.saved = (batch, items, plans, trace)


class Projector:
    async def refresh(self, profile_id, now):
        return 0


def test_candidate_source_never_promotes_audience_or_profile_name_to_topic():
    _, version = profile_without_topics()
    source = DeterministicCandidateSource()

    generated = source.generate(version, window(), BatchRequestConstraints(), 12)

    assert generated == []


def test_explicit_batch_topic_is_valid_authority_without_profile_topics():
    _, version = profile_without_topics()
    source = DeterministicCandidateSource()

    generated = source.generate(
        version,
        window(),
        BatchRequestConstraints(include_topics=("wheel bearings",)),
        8,
    )

    assert len(generated) == 8
    assert {item.topic for item in generated} == {"wheel bearings"}
    assert all(item.topic != AUDIENCE for item in generated)


@pytest.mark.asyncio
async def test_missing_topic_authority_returns_honest_partial_batch():
    profile, version = profile_without_topics()
    repository = PlanningRepo()
    service = BatchPlannerService(
        ProfileRepo(profile, version),
        repository,
        DeterministicCandidateSource(),
        Projector(),
    )

    result = await service.create_batch(
        "tenant-a",
        "logan",
        window(),
        4,
        BatchRequestConstraints(),
        now=NOW,
    )

    assert result.batch.state.value == "PARTIAL"
    assert result.batch.selected_size == 0
    assert result.items == ()
    assert result.plans == ()
    assert result.trace.evaluations == ()
    assert "No usable editorial topic" in result.batch.shortfall_reason
    assert "audience text is never promoted" in result.batch.shortfall_reason
