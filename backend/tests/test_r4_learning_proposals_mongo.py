from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.learning.proposals import LearningProposalService
from application.profiles.patch_service import ProfilePatchService
from domain.learning.models import (
    ConfidenceBand,
    PerformanceDimension,
    PerformanceSignalV1,
    PerformanceSummaryV1,
    canonical_sha256 as learning_sha256,
)
from domain.learning.proposals import (
    HumanProfileDecisionV1,
    LearningDecisionValue,
    deterministic_learning_decision_id,
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
from infrastructure.mongo.learning_proposals import MongoLearningProposalRepository
from infrastructure.mongo.profiles import MongoProfileRepository


NOW = datetime(2026, 9, 14, 4, 10, tzinfo=timezone.utc)


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_r4_learning_{uuid4().hex}"]
    return client, db


def _context(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, actor_id="r4-learning-cert", actor_type="worker")


def _profile_authority(tenant_id: str = "tenant-r4") -> tuple[Profile, ProfileVersion]:
    accepted_at = NOW - timedelta(days=30)
    payload = {
        "schema_version": 2,
        "profile_id": "profile-r4",
        "tenant_id": tenant_id,
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
        "accepted_at": accepted_at,
        "created_at": accepted_at,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id="profile-r4",
        tenant_id=tenant_id,
        current_version=1,
        name="R4 Account",
        status=ProfileStatus.ACTIVE,
        created_at=accepted_at,
        updated_at=accepted_at,
    )
    return profile, version


def _summary() -> PerformanceSummaryV1:
    signal = PerformanceSignalV1(
        signal_id="sig-cloud",
        dimension=PerformanceDimension.CANONICAL_TOPIC,
        key="cloud architecture",
        sample_size=10,
        mean_observation_score=0.8,
        baseline_score=0.5,
        lift=0.3,
        confidence=ConfidenceBand.HIGH,
        planner_weight=1.0,
        note="bounded observational signal",
    )
    payload = {
        "schema_version": 1,
        "summary_id": "perf-r4-mongo",
        "tenant_id": "tenant-r4",
        "profile_id": "profile-r4",
        "policy_version": "s12-performance-v1",
        "window_start": NOW - timedelta(days=7),
        "window_end": NOW,
        "sample_size": 10,
        "eligible_publication_ids": tuple(f"pub-{i}" for i in range(10)),
        "input_snapshot_ids": tuple(f"snapshot-{i}" for i in range(10)),
        "input_digest": "1" * 64,
        "baseline_score": 0.5,
        "signals": (signal,),
        "insufficient_dimensions": (),
        "latest_snapshot_at": NOW,
        "limitations": ("observational association only",),
        "created_at": NOW,
    }
    digest_payload = {key: value for key, value in payload.items() if key != "created_at"}
    return PerformanceSummaryV1(**payload, summary_digest=learning_sha256(digest_payload))


class StaticSummaryService:
    async def rebuild(self, profile_id: str) -> PerformanceSummaryV1:
        assert profile_id == "profile-r4"
        return _summary()


def _service(db, context: TenantContext) -> LearningProposalService:
    profiles = MongoProfileRepository(db, context)
    proposals = MongoLearningProposalRepository(db, context)
    return LearningProposalService(
        summaries=StaticSummaryService(),
        proposals=proposals,
        profiles=profiles,
        profile_patches=ProfilePatchService(profiles),
    )


@pytest.mark.asyncio
async def test_mongo_restart_recovers_persisted_human_decision_without_creating_v3_and_is_tenant_scoped():
    client, db = await _mongo()
    try:
        context_a = _context("tenant-r4")
        context_b = _context("tenant-other")
        profiles_a = MongoProfileRepository(db, context_a)
        profile, version = _profile_authority()
        await profiles_a.create(profile, version)

        first_service = _service(db, context_a)
        proposal = (await first_service.rebuild("profile-r4"))[0]

        # Simulate a backend restart after proposal persistence.
        restarted_proposals = MongoLearningProposalRepository(db, context_a)
        recovered = await restarted_proposals.get(proposal.proposal_id)
        assert recovered is not None
        assert recovered.proposal_digest == proposal.proposal_digest
        assert (await MongoLearningProposalRepository(db, context_b).get(proposal.proposal_id)) is None

        # Persist the human ACCEPTED decision, then simulate the exact crash window
        # before ProfileVersion N+1 is appended / the mutable Profile pointer advances.
        decided_at = NOW + timedelta(minutes=1)
        decision_id = deterministic_learning_decision_id(
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            decision=LearningDecisionValue.ACCEPTED,
            expected_current_version=1,
        )
        decision_payload = {
            "schema_version": 1,
            "decision_id": decision_id,
            "tenant_id": "tenant-r4",
            "profile_id": "profile-r4",
            "proposal_id": proposal.proposal_id,
            "proposal_digest": proposal.proposal_digest,
            "decision": LearningDecisionValue.ACCEPTED,
            "expected_current_version": 1,
            "target_profile_version": 2,
            "decided_at": decided_at,
        }
        decision = HumanProfileDecisionV1(
            **decision_payload,
            decision_digest=learning_sha256(decision_payload),
        )
        persisted_decision = await restarted_proposals.append_decision(decision)
        assert persisted_decision == decision
        assert (await profiles_a.get_profile("profile-r4")).current_version == 1
        assert await profiles_a.get_version("profile-r4", 2) is None

        # New service instance must resume from the immutable decision receipt.
        recovered_service = _service(db, context_a)
        result = await recovered_service.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=LearningDecisionValue.ACCEPTED,
            now=NOW + timedelta(hours=1),
        )
        assert result.decision.decision_digest == decision.decision_digest
        assert result.accepted_profile is not None
        assert result.accepted_profile.version.version == 2
        assert result.accepted_profile.version.accepted_at == decided_at
        assert "cloud architecture" in result.accepted_profile.version.editorial_strategy.topic_families
        target_digest = result.accepted_profile.version.digest

        # A second restart/retry must resolve to exactly the same v2, never create v3.
        second_restart = _service(db, context_a)
        retry = await second_restart.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=LearningDecisionValue.ACCEPTED,
            now=NOW + timedelta(days=1),
        )
        current = await MongoProfileRepository(db, context_a).get_profile("profile-r4")
        assert current is not None and current.current_version == 2
        assert retry.accepted_profile is not None
        assert retry.accepted_profile.version.digest == target_digest
        assert await MongoProfileRepository(db, context_a).get_version("profile-r4", 3) is None

        # Tenant isolation applies to both proposal and decision receipts.
        other_repo = MongoLearningProposalRepository(db, context_b)
        assert await other_repo.get(proposal.proposal_id) is None
        assert await other_repo.get_decision(proposal.proposal_id) is None
    finally:
        await client.drop_database(db.name)
        client.close()
