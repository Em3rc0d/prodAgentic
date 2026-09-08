import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.visual.service import VisualSpecService
from db.mongo import _ensure_mk1_foundation_indexes, _ensure_mk1_production_indexes, _ensure_mk1_visual_indexes
from domain.profiles.models import (
    AccountType,
    AgentPolicy,
    Channel,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    Goal,
    MigrationProvenance,
    NoveltyPolicy,
    Profile,
    ProfileIdentity,
    ProfileStatus,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.production.models import (
    CarouselSlideV1,
    CarouselSpecV1,
    ContentRevisionV1,
    ContentSpecV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
    canonical_sha256 as production_sha256,
)
from domain.tenants.models import TenantContext
from domain.visual.models import canonical_visual_sha256
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.profiles import MongoProfileRepository
from infrastructure.mongo.visual import MongoVisualRepository


NOW = datetime(2026, 9, 8, 17, 30, tzinfo=timezone.utc)


def make_profile() -> tuple[Profile, ProfileVersion]:
    provisional = ProfileVersion(
        profile_id="profile-s4-mongo",
        tenant_id="tenant-s4-a",
        version=1,
        identity=ProfileIdentity(
            name="S4 Mongo Profile",
            account_type=AccountType.NICHE,
            summary="Restart-safe S4 visual fixture",
        ),
        goals=(Goal.EDUCATE,),
        audience=("technical readers",),
        editorial_strategy=EditorialStrategy(topic_families=("systems",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("clear", "technical"), target_language="en"),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "technical")),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.LINKEDIN,),
            default_batch_size=4,
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    version = provisional.model_copy(update={"digest": profile_digest(provisional)})
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


def make_content() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-spec-s4-mongo",
        plan_id="plan-s4-mongo",
        language="en",
        title="Exact lineage",
        hook="Can a visual plan survive a process restart?",
        body="The visual specification should remain immutable and tenant scoped.",
        cta="Inspect the evidence chain.",
        alt_text_draft="Two-page technical carousel about exact visual lineage.",
        format="carousel",
        format_spec=CarouselSpecV1(
            slides=(
                CarouselSlideV1(
                    slide_id="slide-1",
                    role="hook",
                    headline="Freeze visual intent before rendering",
                    body="Bind the plan to exact accepted copy.",
                ),
                CarouselSlideV1(
                    slide_id="slide-2",
                    role="takeaway",
                    headline="Restart without losing lineage",
                    bullets=("Keep immutable specs.", "Advance pointers with CAS."),
                ),
            )
        ),
    )


def make_run_and_revision(version: ProfileVersion, content: ContentSpecV1):
    run = GenerationRunV1(
        run_id="run-s4-mongo",
        tenant_id=version.tenant_id,
        content_id="content-item-s4-mongo",
        profile_id=version.profile_id,
        profile_version=version.version,
        profile_snapshot_digest=version.digest,
        plan_id=content.plan_id,
        plan_digest="b" * 64,
        state=GenerationRunState.VISUAL_PLANNING,
        contract_versions=(
            "ResearchPackV1@1",
            "ContentSpecV1@1",
            "EditorialReviewV1@1",
            "ContentRevisionV1@1",
        ),
        content_spec_ref=content.content_spec_id,
        started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s4-mongo",
        tenant_id=version.tenant_id,
        content_id=run.content_id,
        run_id=run.run_id,
        source=RevisionSource.GENERATION,
        content_spec_ref=content.content_spec_id,
        content_spec_digest=production_sha256(content),
        status=RevisionStatus.DRAFT,
        created_at=NOW,
    )
    return run, revision


@pytest.mark.asyncio
async def test_real_mongodb_s4_visual_lineage_survives_restart_and_is_tenant_scoped():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S4 visual lineage gate")

    database_name = f"prodagentic_s4_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_foundation_indexes(db)
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_visual_indexes(db)

        context = TenantContext(tenant_id="tenant-s4-a", actor_id="operator-s4-a")
        profiles = MongoProfileRepository(db, context)
        production = MongoProductionRepository(db, context)
        visual = MongoVisualRepository(db, context)

        profile, version = make_profile()
        content = make_content()
        run, revision = make_run_and_revision(version, content)

        await profiles.create(profile, version)
        await production.create_run(run)
        await production.save_artifact(
            tenant_id=context.tenant_id,
            run_id=run.run_id,
            artifact_type="ContentSpecV1",
            artifact_id=content.content_spec_id,
            digest=production_sha256(content),
            payload=content.model_dump(mode="json"),
        )
        await production.save_revision(revision)

        service = VisualSpecService(
            production_repository=production,
            profile_repository=profiles,
            visual_repository=visual,
        )
        first = await service.plan_revision(
            tenant_id=context.tenant_id,
            revision_id=revision.revision_id,
        )
        second = await service.plan_revision(
            tenant_id=context.tenant_id,
            revision_id=revision.revision_id,
        )

        assert second.visual_spec.visual_spec_id != first.visual_spec.visual_spec_id
        assert second.visual_spec.supersedes_visual_spec_id == first.visual_spec.visual_spec_id
        assert second.run.state == GenerationRunState.VISUAL_PLANNING
        assert second.revision.status == RevisionStatus.DRAFT
        assert second.revision.asset_refs == ()
        assert second.revision.qa_report_id is None

        # Simulate a full adapter/process restart. No in-memory repository state is reused.
        reopened_profiles = MongoProfileRepository(db, context)
        reopened_production = MongoProductionRepository(db, context)
        reopened_visual = MongoVisualRepository(db, context)

        reloaded_run = await reopened_production.get_run(context.tenant_id, run.run_id)
        reloaded_revision = await reopened_production.get_revision(context.tenant_id, revision.revision_id)
        reloaded_spec = await reopened_visual.get_visual_spec(second.visual_spec.visual_spec_id)
        reloaded_design = await reopened_visual.get_design_profile(second.design_profile.design_profile_id)
        reloaded_profile = await reopened_profiles.get_version(version.profile_id, version.version)

        assert reloaded_run is not None
        assert reloaded_run.visual_spec_ref == second.visual_spec.visual_spec_id
        assert reloaded_run.state == GenerationRunState.VISUAL_PLANNING
        assert reloaded_run.started_at.utcoffset() is not None
        assert reloaded_revision is not None
        assert reloaded_revision.visual_spec_ref == second.visual_spec.visual_spec_id
        assert reloaded_revision.visual_spec_digest == canonical_visual_sha256(second.visual_spec)
        assert reloaded_spec == second.visual_spec
        assert reloaded_design == second.design_profile
        assert reloaded_profile is not None and reloaded_profile.digest == version.digest

        assert await db["visual_specs"].count_documents({"tenant_id": context.tenant_id}) == 2
        assert await db["design_profiles"].count_documents({"tenant_id": context.tenant_id}) == 1
        assert await db["assets"].count_documents({"tenant_id": context.tenant_id}) == 0
        assert await db["publications"].count_documents({"tenant_id": context.tenant_id}) == 0

        other_context = TenantContext(tenant_id="tenant-s4-b", actor_id="operator-s4-b")
        other_production = MongoProductionRepository(db, other_context)
        other_visual = MongoVisualRepository(db, other_context)
        assert await other_production.get_run(other_context.tenant_id, run.run_id) is None
        assert await other_production.get_revision(other_context.tenant_id, revision.revision_id) is None
        assert await other_visual.get_visual_spec(second.visual_spec.visual_spec_id) is None
        assert await other_visual.get_design_profile(second.design_profile.design_profile_id) is None
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_s4_revision_cas_rejects_stale_visual_pointer():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S4 CAS gate")

    database_name = f"prodagentic_s4_cas_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_foundation_indexes(db)
        await _ensure_mk1_production_indexes(db)
        await _ensure_mk1_visual_indexes(db)

        context = TenantContext(tenant_id="tenant-s4-a", actor_id="operator-s4-a")
        profiles = MongoProfileRepository(db, context)
        production = MongoProductionRepository(db, context)
        visual = MongoVisualRepository(db, context)
        profile, version = make_profile()
        content = make_content()
        run, revision = make_run_and_revision(version, content)
        await profiles.create(profile, version)
        await production.create_run(run)
        await production.save_revision(revision)

        first = await visual.bind_revision_visual(
            revision_id=revision.revision_id,
            expected_visual_spec_ref=None,
            visual_spec_ref="vs-first",
            visual_spec_digest="a" * 64,
        )
        assert first is not None and first.visual_spec_ref == "vs-first"

        stale = await visual.bind_revision_visual(
            revision_id=revision.revision_id,
            expected_visual_spec_ref=None,
            visual_spec_ref="vs-stale",
            visual_spec_digest="c" * 64,
        )
        assert stale is None
        persisted = await production.get_revision(context.tenant_id, revision.revision_id)
        assert persisted is not None
        assert persisted.visual_spec_ref == "vs-first"
        assert persisted.visual_spec_digest == "a" * 64
    finally:
        await client.drop_database(database_name)
        client.close()
