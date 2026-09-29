from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.profiles.patch_service import ProfilePatchService
from application.profiles.upgrade_service import ProfileUpgradeService
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
from domain.profiles.upgrades import ProfileUpgradeDecisionValue, malformed_topic_family
from domain.tenants.models import TenantContext
from infrastructure.mongo.profile_upgrades import MongoProfileUpgradeDecisionRepository
from infrastructure.mongo.profiles import MongoProfileRepository


NOW = datetime(2026, 9, 14, 5, 0, tzinfo=timezone.utc)
RAW_TOPIC = (
    "people to wants pass the systems engineer career i m going to help their because "
    "i m systems engineer student in his last semester"
)


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_r4_upgrade_{uuid4().hex}"]
    return client, db


def _context(tenant_id: str = "tenant-r4") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, actor_id="r4-upgrade-cert", actor_type="worker")


def _authority(topic_families=(RAW_TOPIC,), *, tenant_id="tenant-r4"):
    created = NOW - timedelta(days=30)
    payload = {
        "schema_version": 2,
        "profile_id": "profile-r4",
        "tenant_id": tenant_id,
        "version": 1,
        "identity": ProfileIdentity(
            name="EM3RC0D fixture",
            account_type="personal_brand",
            summary=RAW_TOPIC,
        ),
        "goals": ("educate", "grow", "build_authority"),
        "audience": (RAW_TOPIC,),
        "editorial_strategy": EditorialStrategy(topic_families=topic_families),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(
            voice_traits=("direct", "educational"),
            hook_tendencies=("question",),
            target_language="es",
        ),
        "claim_policy": ClaimPolicy(),
        "visual_system": VisualSystem(traits=("technical", "bold")),
        "publishing_preferences": PublishingPreferences(
            channels=("manual_export",), default_batch_size=4
        ),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(source="USER_ACCEPTED"),
        "accepted_at": created,
        "created_at": created,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id="profile-r4",
        tenant_id=tenant_id,
        current_version=1,
        name="EM3RC0D fixture",
        status=ProfileStatus.ACTIVE,
        created_at=created,
        updated_at=created,
    )
    return profile, version


def _service(db, context):
    profiles = MongoProfileRepository(db, context)
    return ProfileUpgradeService(
        profiles=profiles,
        decisions=MongoProfileUpgradeDecisionRepository(db, context),
        profile_patches=ProfilePatchService(profiles),
    )


def test_malformed_profile_fixture_is_detected_and_compacted_without_inventing_new_vertical_topics():
    _, version = _authority()
    assert malformed_topic_family(RAW_TOPIC)
    proposal = ProfileUpgradeService.proposal_for_version(version)
    assert proposal is not None
    assert proposal.removed_topic_families == (RAW_TOPIC,)
    assert RAW_TOPIC not in proposal.proposed_topic_families
    assert proposal.proposed_topic_families == ("systems engineer",)
    assert all(len(item.split()) <= 6 for item in proposal.proposed_topic_families)


def test_clean_compact_profile_has_no_upgrade_proposal():
    _, version = _authority(("systems engineering", "programming", "databases"))
    assert ProfileUpgradeService.proposal_for_version(version) is None


@pytest.mark.asyncio
async def test_upgrade_acceptance_creates_v2_preserves_v1_and_retry_after_restart_never_creates_v3():
    client, db = await _mongo()
    try:
        context = _context()
        profiles = MongoProfileRepository(db, context)
        profile, version1 = _authority()
        await profiles.create(profile, version1)

        first_service = _service(db, context)
        proposal = await first_service.propose("profile-r4")
        assert proposal is not None
        accepted = await first_service.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=ProfileUpgradeDecisionValue.ACCEPTED,
            now=NOW + timedelta(minutes=1),
        )
        assert accepted.accepted_profile is not None
        assert accepted.accepted_profile.version.version == 2
        assert accepted.accepted_profile.version.editorial_strategy.topic_families == ("systems engineer",)

        historical = await profiles.get_version("profile-r4", 1)
        assert historical is not None
        assert historical.digest == version1.digest
        assert historical.editorial_strategy.topic_families == (RAW_TOPIC,)

        restarted = _service(db, context)
        retry = await restarted.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=ProfileUpgradeDecisionValue.ACCEPTED,
            now=NOW + timedelta(days=1),
        )
        assert retry.accepted_profile is not None
        assert retry.accepted_profile.version.digest == accepted.accepted_profile.version.digest
        current = await MongoProfileRepository(db, context).get_profile("profile-r4")
        assert current is not None and current.current_version == 2
        assert await MongoProfileRepository(db, context).get_version("profile-r4", 3) is None

        other = MongoProfileUpgradeDecisionRepository(db, _context("tenant-other"))
        assert await other.get(proposal.proposal_id) is None
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_rejected_upgrade_is_auditable_and_does_not_mutate_profile():
    client, db = await _mongo()
    try:
        context = _context()
        profiles = MongoProfileRepository(db, context)
        profile, _ = _authority()
        await profiles.create(profile, _authority()[1])
        service = _service(db, context)
        proposal = await service.propose("profile-r4")
        assert proposal is not None
        result = await service.decide(
            tenant_id="tenant-r4",
            profile_id="profile-r4",
            proposal_digest=proposal.proposal_digest,
            expected_current_version=1,
            decision=ProfileUpgradeDecisionValue.REJECTED,
            now=NOW + timedelta(minutes=2),
        )
        assert result.accepted_profile is None
        persisted = await MongoProfileUpgradeDecisionRepository(db, context).get(proposal.proposal_id)
        assert persisted is not None
        assert persisted.decision is ProfileUpgradeDecisionValue.REJECTED
        current = await profiles.get_profile("profile-r4")
        assert current is not None and current.current_version == 1
    finally:
        await client.drop_database(db.name)
        client.close()
