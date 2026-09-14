from __future__ import annotations

import hashlib
import os
from base64 import b64decode
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.rendering.generated_assets import GeneratedAssetResolver, GeneratedAssetResolutionError
from application.visual.design_profile import derive_design_profile
from application.visual.planner import build_visual_spec
from domain.production.models import ContentSpecV1, SingleImageSpecV1
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
    ProfileIdentity,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest as profile_digest,
)
from domain.rendering.ports import GeneratedImageBytes
from domain.tenants.models import TenantContext
from infrastructure.assets.r4_filesystem import R4FilesystemAssetStore
from infrastructure.mongo.rendering_r4 import MongoR4RenderingRepository

NOW = datetime(2026, 9, 14, 17, 0, tzinfo=timezone.utc)
PNG = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=")


async def _mongo():
    uri = os.getenv("MONGO_TEST_URI", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client[f"prodagentic_r4_visual_recovery_{uuid4().hex}"]
    return client, db


def _context(tenant_id: str = "tenant-r4") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, actor_id="r4-visual-cert", actor_type="worker")


def _profile() -> ProfileVersion:
    provisional = ProfileVersion(
        profile_id="profile-r4",
        tenant_id="tenant-r4",
        version=2,
        identity=ProfileIdentity(
            name="EM3RC0D",
            account_type=AccountType.EDUCATION,
            summary="Practical systems engineering guidance",
        ),
        goals=(Goal.EDUCATE, Goal.BUILD_AUTHORITY),
        audience=("systems engineering students",),
        editorial_strategy=EditorialStrategy(topic_families=("software architecture",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("direct", "practical"), target_language="es"),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "bold")),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.LINKEDIN, Channel.MANUAL_EXPORT), default_batch_size=4
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return provisional.model_copy(update={"digest": profile_digest(provisional)})


def _content() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-r4-recovery",
        plan_id="plan-r4-recovery",
        language="es",
        title="La arquitectura se rompe antes del diagrama",
        hook="Tu arquitectura puede fallar aunque el diagrama se vea perfecto.",
        body="Define autoridad, fallo y recuperación antes de añadir más componentes.",
        cta="¿Qué decisión sigue abierta?",
        hashtags=("#SoftwareArchitecture",),
        alt_text_draft="Editorial visual about architecture decisions.",
        format="single_image",
        format_spec=SingleImageSpecV1(
            headline="La arquitectura se rompe antes del diagrama",
            supporting_copy=("Define autoridad", "Diseña el fallo", "Prueba recuperación"),
            footer="EM3RC0D",
        ),
        claims_used=(),
    )


class CountingGenerator:
    def __init__(self):
        self.calls = 0

    async def generate(self, *, prompt: str, aspect_ratio: str):
        self.calls += 1
        assert aspect_ratio == "4:5"
        assert "DO NOT render any words" in prompt
        return GeneratedImageBytes(
            data=PNG,
            content_type="image/png",
            provider="cert-provider",
            model="cert-image-v1",
        )


@pytest.mark.asyncio
async def test_generated_visual_survives_repository_restart_and_no_longer_needs_provider(tmp_path):
    client, db = await _mongo()
    try:
        context = _context()
        profile = _profile()
        content = _content()
        design = derive_design_profile(profile)
        spec = build_visual_spec(
            visual_spec_id="vs-r4-recovery",
            revision_id="revision-r4-recovery",
            content=content,
            design_profile=design,
            generated_visuals_enabled=True,
        )
        store = R4FilesystemAssetStore(tmp_path)
        generator = CountingGenerator()

        first_repo = MongoR4RenderingRepository(db, context)
        first = await GeneratedAssetResolver(
            repository=first_repo,
            asset_store=store,
            image_generator=generator,
        ).resolve(
            tenant_id=context.tenant_id,
            revision_id="revision-r4-recovery",
            visual_spec=spec,
            content=content,
            design_profile=design,
        )
        requirement_id = spec.asset_requirements[0].requirement_id
        source_asset_id = first[requirement_id].source_asset_id
        expected_sha = hashlib.sha256(PNG).hexdigest()
        assert generator.calls == 1
        assert first[requirement_id].sha256 == expected_sha

        # New repository/service objects model a backend restart. Provider access
        # is intentionally absent: frozen owned bytes must remain sufficient.
        restarted_repo = MongoR4RenderingRepository(db, context)
        recovered = await GeneratedAssetResolver(
            repository=restarted_repo,
            asset_store=store,
            image_generator=None,
        ).resolve(
            tenant_id=context.tenant_id,
            revision_id="revision-r4-recovery",
            visual_spec=spec,
            content=content,
            design_profile=design,
        )
        assert recovered[requirement_id].source_asset_id == source_asset_id
        assert recovered[requirement_id].data == PNG
        assert recovered[requirement_id].sha256 == expected_sha

        # Tenant-scoped repository must not expose the source authority elsewhere.
        other_repo = MongoR4RenderingRepository(db, _context("tenant-other"))
        assert await other_repo.get_source_asset(source_asset_id) is None

        persisted = await restarted_repo.get_source_asset(source_asset_id)
        assert persisted is not None
        assert await store.verify(persisted.storage_key, persisted.sha256)
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_restart_fails_closed_when_owned_generated_bytes_are_tampered(tmp_path):
    client, db = await _mongo()
    try:
        context = _context()
        profile = _profile()
        content = _content()
        design = derive_design_profile(profile)
        spec = build_visual_spec(
            visual_spec_id="vs-r4-tamper",
            revision_id="revision-r4-tamper",
            content=content,
            design_profile=design,
            generated_visuals_enabled=True,
        )
        store = R4FilesystemAssetStore(tmp_path)
        repo = MongoR4RenderingRepository(db, context)
        resolved = await GeneratedAssetResolver(
            repository=repo,
            asset_store=store,
            image_generator=CountingGenerator(),
        ).resolve(
            tenant_id=context.tenant_id,
            revision_id="revision-r4-tamper",
            visual_spec=spec,
            content=content,
            design_profile=design,
        )
        requirement_id = spec.asset_requirements[0].requirement_id
        metadata = await repo.get_source_asset(resolved[requirement_id].source_asset_id)
        assert metadata is not None

        path = tmp_path / metadata.storage_key
        path.write_bytes(b"tampered")

        with pytest.raises(GeneratedAssetResolutionError, match="read-back verification"):
            await GeneratedAssetResolver(
                repository=MongoR4RenderingRepository(db, context),
                asset_store=store,
                image_generator=None,
            ).resolve(
                tenant_id=context.tenant_id,
                revision_id="revision-r4-tamper",
                visual_spec=spec,
                content=content,
                design_profile=design,
            )
    finally:
        await client.drop_database(db.name)
        client.close()
