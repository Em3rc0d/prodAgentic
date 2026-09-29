from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from application.learning.proposals import LearningProposalService, LearningProposalStale
from application.profiles.patch_service import ProfilePatchService
from domain.learning.models import (
    ConfidenceBand,
    PerformanceDimension,
    PerformanceSignalV1,
    PerformanceSummaryV1,
    canonical_sha256 as learning_sha256,
)
from domain.learning.proposals import LearningDecisionValue, LearningProposalType
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


NOW = datetime(2026, 9, 13, 22, 30, tzinfo=timezone.utc)


def _profile_authority():
    payload = {
        "schema_version": 2,
        "profile_id": "profile-r4",
        "tenant_id": "tenant-r4",
        "version": 1,
        "identity": ProfileIdentity(
            name="R4 Account",
            account_type="education",
            summary="Systems engineering education account",
        ),
        "goals": ("educate", "grow"),
        "audience": ("systems engineering students",),
        "editorial_strategy": EditorialStrategy(topic_families=("programming",)),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(
            voice_traits=("direct", "educational"),
            hook_tendencies=("question",),
            target_language="es",
        ),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(traits=("technical",)),
        "publishing_preferences": PublishingPreferences(
            channels=("manual_export",),
            default_batch_size=4,
        ),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": NOW - timedelta(days=30),
        "created_at": NOW - timedelta(days=30),
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id="profile-r4",
        tenant_id="tenant-r4",
        current_version=1,
        name="R4 Account",
        status=ProfileStatus.ACTIVE,
        created_at=NOW - timedelta(days=30),
        updated_at=NOW - timedelta(days=30),
    )
    return profile, version


def _signal(
    *,
    signal_id: str,
    dimension: PerformanceDimension,
    key: str,
    confidence: ConfidenceBand = ConfidenceBand.MEDIUM,
    sample_size: int = 5,
    lift: float = 0.2,
):
    weight = 1.0 if confidence is ConfidenceBand.HIGH else 0.5 if confidence is ConfidenceBand.MEDIUM else 0.0
    return PerformanceSignalV1(
        signal_id=signal_id,
        dimension=dimension,
        key=key,
        sample_size=sample_size,
        mean_observation_score=0.7,
        baseline_score=0.5,
        lift=lift,
        confidence=confidence,
        planner_weight=weight,
        note="bounded observational signal",
    )


def _summary(*signals: PerformanceSignalV1, sample_size: int = 5) -> PerformanceSummaryV1:
    payload = {
        "schema_version": 1,
        "summary_id": "perf-r4",
        "tenant_id": "tenant-r4",
        "profile_id": "profile-r4",
        "policy_version": "s12-performance-v1",
        "window_start": NOW - timedelta(days=7),
        "window_end": NOW,
        "sample_size": sample_size,
        "eligible_publication_ids": tuple(f"pub-{index}" for index in range(sample_size)),
        "input_snapshot_ids": tuple(f"snapshot-{index}" for index in range(sample_size)),
        "input_digest": "1" * 64,
        "baseline_score": 0.5,
        "signals": tuple(signals),
        "insufficient_dimensions": (),
        "latest_snapshot_at": NOW,
        "limitations": ("observational association only",),
        "created_at": NOW,
    }
    digest_payload = {key: value for key, value in payload.items() if key != "created_at"}
    return PerformanceSummaryV1(
        **payload,
        summary_digest=learning_sha256(digest_payload),
    )


class StaticSummaryService:
    def __init__(self, summary):
        self.summary = summary

    async def rebuild(self, profile_id):
        assert profile_id == "profile-r4"
        return self.summary


class MemoryProposalRepository:
    def __init__(self):
        self.proposals = {}
        self.decisions = {}

    async def append(self, proposal):
        existing = self.proposals.get(proposal.proposal_id)
        if existing is not None:
            assert existing.proposal_digest == proposal.proposal_digest
            return existing
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    async def get(self, proposal_id):
        return self.proposals.get(proposal_id)

    async def list_for_profile(self, profile_id):
        return [item for item in self.proposals.values() if item.profile_id == profile_id]

    async def append_decision(self, decision):
        existing = self.decisions.get(decision.proposal_id)
        if existing is not None:
            return existing
        self.decisions[decision.proposal_id] = decision
        return decision

    async def get_decision(self, proposal_id):
        return self.decisions.get(proposal_id)


class MemoryProfileRepository:
    def __init__(self):
        self.profile, version = _profile_authority()
        self.versions = {1: version}

    async def get_profile(self, profile_id):
        return self.profile if profile_id == self.profile.profile_id else None

    async def get_version(self, profile_id, version):
        if profile_id != self.profile.profile_id:
            return None
        return self.versions.get(version)

    async def append_version(self, profile, version, expected_version):
        if self.profile.current_version != expected_version:
            return False
        existing = self.versions.get(version.version)
        if existing is not None:
            return existing.digest == version.digest
        self.versions[version.version] = version
        self.profile = profile
        return True


def _service(summary):
    profiles = MemoryProfileRepository()
    proposals = MemoryProposalRepository()
    service = LearningProposalService(
        summaries=StaticSummaryService(summary),
        proposals=proposals,
        profiles=profiles,
        profile_patches=ProfilePatchService(profiles),
    )
    return service, profiles, proposals


@pytest.mark.asyncio
async def test_learning_proposals_require_repeated_medium_or_high_confidence_evidence():
    low = _signal(
        signal_id="sig-low",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="cloud",
        confidence=ConfidenceBand.LOW,
        sample_size=3,
        lift=0.3,
    )
    service, _, _ = _service(_summary(low, sample_size=3))
    assert await service.rebuild("profile-r4") == ()


@pytest.mark.asyncio
async def test_learning_proposals_are_bounded_to_existing_profile_fields_and_idempotent():
    topic = _signal(
        signal_id="sig-topic",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="cloud architecture",
    )
    hook = _signal(
        signal_id="sig-hook",
        dimension=PerformanceDimension.HOOK_PATTERN,
        key="counterintuitive",
        confidence=ConfidenceBand.HIGH,
        sample_size=10,
        lift=0.25,
    )
    already_known = _signal(
        signal_id="sig-known",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="programming",
        confidence=ConfidenceBand.HIGH,
        sample_size=10,
        lift=0.4,
    )
    service, _, proposals = _service(_summary(topic, hook, already_known, sample_size=10))

    first = await service.rebuild("profile-r4")
    second = await service.rebuild("profile-r4")
    assert first == second
    assert len(proposals.proposals) == 2
    assert {item.proposal_type for item in first} == {
        LearningProposalType.PROMOTE_TOPIC_FAMILY,
        LearningProposalType.PREFER_HOOK_TENDENCY,
    }
    assert all(item.profile_version == 1 for item in first)
    assert all(item.profile_digest for item in first)


@pytest.mark.asyncio
async def test_accepting_semantic_learning_creates_exact_new_profile_version_and_retry_is_idempotent():
    topic = _signal(
        signal_id="sig-topic",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="cloud architecture",
        confidence=ConfidenceBand.HIGH,
        sample_size=10,
        lift=0.3,
    )
    service, profiles, _ = _service(_summary(topic, sample_size=10))
    proposal = (await service.rebuild("profile-r4"))[0]
    old_digest = profiles.versions[1].digest

    first = await service.decide(
        tenant_id="tenant-r4",
        profile_id="profile-r4",
        proposal_id=proposal.proposal_id,
        proposal_digest=proposal.proposal_digest,
        expected_current_version=1,
        decision=LearningDecisionValue.ACCEPTED,
        now=NOW + timedelta(minutes=1),
    )
    assert first.accepted_profile is not None
    assert first.accepted_profile.version.version == 2
    assert first.accepted_profile.version.accepted_at == NOW + timedelta(minutes=1)
    assert "cloud architecture" in first.accepted_profile.version.editorial_strategy.topic_families
    assert profiles.versions[1].digest == old_digest
    assert profiles.profile.current_version == 2

    retry = await service.decide(
        tenant_id="tenant-r4",
        profile_id="profile-r4",
        proposal_id=proposal.proposal_id,
        proposal_digest=proposal.proposal_digest,
        expected_current_version=1,
        decision=LearningDecisionValue.ACCEPTED,
        now=NOW + timedelta(hours=1),
    )
    assert retry.decision == first.decision
    assert retry.accepted_profile is not None
    assert retry.accepted_profile.version.digest == first.accepted_profile.version.digest
    assert set(profiles.versions) == {1, 2}


@pytest.mark.asyncio
async def test_rejecting_learning_is_auditable_and_does_not_mutate_profile():
    hook = _signal(
        signal_id="sig-hook",
        dimension=PerformanceDimension.HOOK_PATTERN,
        key="counterintuitive",
        confidence=ConfidenceBand.HIGH,
        sample_size=10,
        lift=0.3,
    )
    service, profiles, _ = _service(_summary(hook, sample_size=10))
    proposal = (await service.rebuild("profile-r4"))[0]

    result = await service.decide(
        tenant_id="tenant-r4",
        profile_id="profile-r4",
        proposal_id=proposal.proposal_id,
        proposal_digest=proposal.proposal_digest,
        expected_current_version=1,
        decision=LearningDecisionValue.REJECTED,
        now=NOW + timedelta(minutes=1),
    )
    assert result.accepted_profile is None
    assert result.decision.decision is LearningDecisionValue.REJECTED
    assert profiles.profile.current_version == 1
    assert set(profiles.versions) == {1}


@pytest.mark.asyncio
async def test_accepted_proposal_fails_closed_if_profile_advanced_first():
    topic = _signal(
        signal_id="sig-topic",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="cloud architecture",
        confidence=ConfidenceBand.HIGH,
        sample_size=10,
        lift=0.3,
    )
    service, profiles, proposals = _service(_summary(topic, sample_size=10))
    proposal = (await service.rebuild("profile-r4"))[0]
    profiles.profile = profiles.profile.model_copy(update={"current_version": 2})

    with pytest.raises(LearningProposalStale):
        await service.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=LearningDecisionValue.ACCEPTED,
            now=NOW + timedelta(minutes=1),
        )
    assert proposal.proposal_id not in proposals.decisions
