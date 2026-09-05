import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.planning import BatchPlannerService
from application.profiles import DeterministicProfileAnalyzer, ProfileService
from db.mongo import _ensure_mk1_foundation_indexes, _ensure_mk1_planning_indexes
from domain.planning.models import BatchRequestConstraints, IdeaCandidateV1, TargetWindow
from domain.profiles.models import ProfileSetup
from domain.tenants.models import TenantContext
from infrastructure.mongo.editorial_memory import MongoEditorialMemoryProjector
from infrastructure.mongo.planning import MongoPlanningRepository
from infrastructure.mongo.profiles import MongoProfileRepository


NOW = datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc)


class FixtureCandidateSource:
    def __init__(self):
        self.pool_size = None

    def generate(self, profile, target_window, constraints, target_pool_size):
        self.pool_size = target_pool_size
        values = [
            ("repeat-tires", "symptom", "llantas", "diagnosis", "question", "single_image"),
            ("fresh-brakes", "safety", "brake fluid", "safety", "warning", "single_image"),
            ("fresh-bearing", "mechanical_explainer", "wheel bearing", "how it works", "diagram_flow", "infographic"),
            ("fresh-filter", "maintenance", "air filter", "maintenance", "checklist", "carousel"),
            ("fresh-align", "symptom", "steering alignment", "diagnosis", "story", "text"),
            ("fresh-coolant", "maintenance", "cooling system", "how it works", "question", "carousel"),
            ("fresh-suspension", "mechanical_explainer", "suspension", "tradeoff", "counterintuitive", "infographic"),
            ("fresh-lights", "safety", "headlights", "safety", "numbered", "single_image"),
            ("fresh-wipers", "maintenance", "wipers", "maintenance", "story", "text"),
            ("fresh-fuses", "mechanical_explainer", "fuses", "how it works", "diagram_flow", "infographic"),
            ("fresh-belts", "maintenance", "accessory belt", "maintenance", "checklist", "carousel"),
            ("fresh-steering", "symptom", "power steering", "diagnosis", "question", "text"),
        ]
        return [
            IdeaCandidateV1(
                candidate_id=candidate_id,
                role=role,
                topic=topic,
                angle=angle,
                hook_pattern=hook,
                target_effect="useful outcome",
                tentative_format=fmt,
                rationale=f"fixture {role} / {angle}",
                claim_risk="low",
            )
            for candidate_id, role, topic, angle, hook, fmt in values[:target_pool_size]
        ]


def setup():
    return ProfileSetup(
        name="Mongo S2 Profile",
        account_type="education",
        goals=("educate", "build_authority"),
        audience="drivers learning practical car care",
        voice=("direct", "simple"),
        batch_size=4,
        channels=("manual_export",),
    )


def window():
    return TargetWindow(
        start_at=NOW + timedelta(days=1),
        end_at=NOW + timedelta(days=2),
        timezone="America/Lima",
    )


@pytest.mark.asyncio
async def test_real_mongodb_s2_rebuilds_legacy_memory_blocks_repeat_and_persists_frozen_batch():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S2 planning gate")

    database_name = f"prodagentic_s2_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_foundation_indexes(db)
        await _ensure_mk1_planning_indexes(db)

        context = TenantContext(tenant_id="tenant-a", actor_id="operator-a")
        profile_repository = MongoProfileRepository(db, context)
        profile_service = ProfileService(profile_repository, DeterministicProfileAnalyzer())
        profile_setup = setup()
        created = await profile_service.create(
            "tenant-a",
            profile_setup,
            profile_service.propose(profile_setup).proposal_digest,
        )

        await db["content_runs"].insert_one({
            "tenant_id": "tenant-a",
            "run_id": "legacy-published-tires",
            "content_profile_id": created.profile.profile_id,
            "status": "PUBLISHED",
            "topic": "neumáticos",
            "idea": "diagnosis",
            "style": "question",
            "updated_at": NOW - timedelta(days=1),
            "publication": {
                "status": "PUBLISHED",
                "started_at": NOW - timedelta(days=1),
                "completed_at": NOW - timedelta(days=1),
            },
        })

        planning_repository = MongoPlanningRepository(db, context)
        projector = MongoEditorialMemoryProjector(db, context, planning_repository)
        source = FixtureCandidateSource()
        planner = BatchPlannerService(
            profile_repository,
            planning_repository,
            source,
            projector,
        )
        result = await planner.create_batch(
            "tenant-a",
            created.profile.profile_id,
            window(),
            4,
            BatchRequestConstraints(),
            now=NOW,
        )

        assert source.pool_size == 12
        assert result.batch.selected_size == 4
        assert result.batch.profile_version == created.version.version
        assert result.batch.profile_snapshot_digest == created.version.digest
        assert result.batch.strategy_snapshot.performance_summary_version is None
        assert "repeat-tires" not in {plan.plan.candidate_id for plan in result.plans}
        repeated = next(
            evaluation
            for evaluation in result.trace.evaluations
            if evaluation.candidate.candidate_id == "repeat-tires"
        )
        assert repeated.novelty.verdict.value == "BLOCKED"
        assert repeated.novelty.matched_content_ids == ("legacy-published-tires",)

        assert await db["batches"].count_documents({"tenant_id": "tenant-a", "batch_id": result.batch.batch_id}) == 1
        assert await db["content_items"].count_documents({"tenant_id": "tenant-a", "batch_id": result.batch.batch_id}) == 4
        assert await db["content_plans"].count_documents({"tenant_id": "tenant-a", "batch_id": result.batch.batch_id}) == 4
        assert await db["planning_traces"].count_documents({"tenant_id": "tenant-a", "batch_id": result.batch.batch_id}) == 1
        assert await db["editorial_memory"].count_documents({"tenant_id": "tenant-a", "profile_id": created.profile.profile_id}) == 1

        # Rebuild is an idempotent read-model operation, not append-only drift.
        await projector.refresh(created.profile.profile_id, NOW + timedelta(minutes=5))
        assert await db["editorial_memory"].count_documents({"tenant_id": "tenant-a", "profile_id": created.profile.profile_id}) == 1

        other_context = TenantContext(tenant_id="tenant-b", actor_id="operator-b")
        other_repository = MongoPlanningRepository(db, other_context)
        assert await other_repository.get_batch(result.batch.batch_id) is None
        assert await other_repository.list_batch_items(result.batch.batch_id) == []
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_s2_batch_commit_marker_compensates_ordinary_precommit_failure():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S2 commit-boundary gate")

    database_name = f"prodagentic_s2_commit_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_foundation_indexes(db)
        await _ensure_mk1_planning_indexes(db)

        context = TenantContext(tenant_id="tenant-a", actor_id="operator-a")
        profile_repository = MongoProfileRepository(db, context)
        profile_service = ProfileService(profile_repository, DeterministicProfileAnalyzer())
        profile_setup = setup()
        created = await profile_service.create(
            "tenant-a",
            profile_setup,
            profile_service.propose(profile_setup).proposal_digest,
        )

        planning_repository = MongoPlanningRepository(db, context)
        projector = MongoEditorialMemoryProjector(db, context, planning_repository)
        planner = BatchPlannerService(
            profile_repository,
            planning_repository,
            FixtureCandidateSource(),
            projector,
        )

        async def fail_commit_marker(*args, **kwargs):
            raise RuntimeError("simulated Batch commit marker failure")

        planning_repository.batches.insert_one = fail_commit_marker
        with pytest.raises(RuntimeError, match="simulated Batch commit marker failure"):
            await planner.create_batch(
                "tenant-a",
                created.profile.profile_id,
                window(),
                4,
                BatchRequestConstraints(),
                now=NOW,
            )

        assert await db["batches"].count_documents({"tenant_id": "tenant-a"}) == 0
        assert await db["content_items"].count_documents({"tenant_id": "tenant-a"}) == 0
        assert await db["content_plans"].count_documents({"tenant_id": "tenant-a"}) == 0
        assert await db["planning_traces"].count_documents({"tenant_id": "tenant-a"}) == 0
    finally:
        await client.drop_database(database_name)
        client.close()
