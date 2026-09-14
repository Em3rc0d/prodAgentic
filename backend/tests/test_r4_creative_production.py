from __future__ import annotations

import hashlib
from base64 import b64decode
from datetime import datetime, timezone

import pytest

from application.content_quality.policy import blocking_publishability_issues, strict_publishability_issues
from application.production.r4_service import R4StructuredAgentCellService
from application.production.service import ProductionContractViolation
from application.rendering.copy_resolver import build_renderer_request
from application.rendering.generated_assets import GeneratedAssetResolver, ResolvedSourceAsset
from application.visual.design_profile import derive_design_profile
from application.visual.planner import build_visual_spec
from domain.planning.models import ContentPlanV1
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
from domain.production.models import (
    ContentSpecV1,
    EditorialReviewV1,
    EditorialVerdict,
    ResearchPackV1,
    ResearchVerdict,
    SingleImageSpecV1,
)
from domain.rendering.models import canonical_render_sha256
from domain.rendering.ports import GeneratedImageBytes
from domain.visual.models import AssetRequirementKind, ImageBlockV1, RenderStrategy
from infrastructure.assets.r4_filesystem import R4FilesystemAssetStore


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
# Small valid PNG. Provider adapters own deeper MIME/magic validation; this
# fixture exercises R4 ownership, hashing, idempotency and render binding.
PNG = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=")


def make_profile() -> ProfileVersion:
    value = ProfileVersion(
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
        editorial_strategy=EditorialStrategy(topic_families=("software architecture", "systems engineering")),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(
            voice_traits=("direct", "practical"),
            target_language="es",
            hook_tendencies=("question",),
            cta_style="question",
        ),
        claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=("clean", "bold")),
        publishing_preferences=PublishingPreferences(
            channels=(Channel.LINKEDIN, Channel.MANUAL_EXPORT),
            default_batch_size=4,
        ),
        agent_policy=AgentPolicy(),
        provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW,
        created_at=NOW,
        digest="0" * 64,
    )
    return value.model_copy(update={"digest": profile_digest(value)})


def make_plan() -> ContentPlanV1:
    return ContentPlanV1(
        plan_id="plan-r4",
        candidate_id="candidate-r4",
        profile_id="profile-r4",
        profile_version=2,
        role="education",
        canonical_topic="software.architecture",
        subtopics=("software architecture",),
        angle="worked example",
        target_effect="understanding",
        format="single_image",
        hook_pattern="counterintuitive",
        visual_pattern_hint=None,
        novelty_result_ref="novelty-r4",
        planning_rationale="R4 fixture",
    )


def good_content() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-r4",
        plan_id="plan-r4",
        language="es",
        title="La arquitectura se rompe antes del diagrama",
        hook="Tu arquitectura puede fallar aunque el diagrama se vea perfecto.",
        body=(
            "El problema aparece cuando una decisión importante queda sin dueño: quién valida el dato, "
            "qué ocurre durante un fallo y qué evidencia confirma la recuperación. Diseña esas decisiones "
            "antes de añadir más componentes."
        ),
        cta="¿Qué decisión de tu arquitectura sigue abierta hoy?",
        hashtags=("#SoftwareArchitecture", "#IngenieriaDeSistemas"),
        alt_text_draft="Editorial visual about architecture decisions and failure ownership.",
        format="single_image",
        format_spec=SingleImageSpecV1(
            headline="La arquitectura se rompe antes del diagrama",
            supporting_copy=("Define autoridad", "Diseña el fallo", "Prueba la recuperación"),
            footer="EM3RC0D",
        ),
        claims_used=(),
    )


def research() -> ResearchPackV1:
    return ResearchPackV1(
        research_id="research-r4",
        plan_id="plan-r4",
        verdict=ResearchVerdict.GO,
        key_points=("authority", "failure recovery"),
        claims=(),
        evidence=(),
    )


def approved_review() -> EditorialReviewV1:
    return EditorialReviewV1(
        review_id="review-r4",
        verdict=EditorialVerdict.APPROVE_TEXT,
        brand_match="pass",
        clarity="pass",
        hook_strength="pass",
        factual_consistency="pass",
        platform_fit="pass",
        issues=(),
    )


def test_real_r4_promotes_known_template_slop_to_fail_closed_quality_gate():
    profile = make_profile()
    plan = make_plan()
    weak = good_content().model_copy(
        update={
            "hook": "Para avanzar con software architecture, empieza por una decisión concreta, no por una lista infinita.",
            "body": (
                "Usa un marco simple: define la decisión, elimina lo que no cambia esa decisión y termina con una siguiente acción. "
                "Esta segunda oración mantiene longitud suficiente pero no añade sustancia específica."
            ),
        }
    )

    assert not blocking_publishability_issues(content=weak, plan=plan, profile=profile)
    strict_codes = {issue.code for issue in strict_publishability_issues(content=weak, plan=plan, profile=profile)}
    assert "copy.generic_hook" in strict_codes

    with pytest.raises(ProductionContractViolation, match="strict publishability"):
        R4StructuredAgentCellService._verify_review(plan, profile, research(), weak, approved_review())


def test_r4_visualspec_requires_generated_image_but_keeps_copy_authoritative():
    profile = make_profile()
    design = derive_design_profile(profile)
    content = good_content()
    spec = build_visual_spec(
        visual_spec_id="vs-r4",
        revision_id="revision-r4",
        content=content,
        design_profile=design,
        generated_visuals_enabled=True,
    )

    assert spec.render_strategy == RenderStrategy.GENERATED_VISUAL_PLUS_COMPOSITE
    assert len(spec.asset_requirements) == 1
    assert spec.asset_requirements[0].kind == AssetRequirementKind.GENERATED_IMAGE
    images = [block for block in spec.pages[0].blocks if isinstance(block, ImageBlockV1)]
    assert len(images) == 1
    assert images[0].asset_requirement_ref == spec.asset_requirements[0].requirement_id
    assert any(getattr(block, "copy_ref", None) == "content_spec.format_spec.headline" for block in spec.pages[0].blocks)


class FakeRenderingRepository:
    def __init__(self):
        self.source_assets = {}

    async def get_source_asset(self, source_asset_id):
        return self.source_assets.get(source_asset_id)

    async def save_source_asset(self, asset):
        previous = self.source_assets.get(asset.source_asset_id)
        if previous is not None and previous != asset:
            raise AssertionError("identity collision")
        self.source_assets[asset.source_asset_id] = asset


class FakeImageGenerator:
    def __init__(self):
        self.calls = 0

    async def generate(self, *, prompt: str, aspect_ratio: str):
        self.calls += 1
        assert "DO NOT render any words" in prompt
        assert aspect_ratio == "4:5"
        return GeneratedImageBytes(data=PNG, content_type="image/png", provider="fake", model="fake-image-v1")


@pytest.mark.asyncio
async def test_generated_source_asset_is_owned_hash_bound_and_reused(tmp_path):
    profile = make_profile()
    design = derive_design_profile(profile)
    content = good_content()
    spec = build_visual_spec(
        visual_spec_id="vs-r4-owned",
        revision_id="revision-r4-owned",
        content=content,
        design_profile=design,
        generated_visuals_enabled=True,
    )
    repository = FakeRenderingRepository()
    store = R4FilesystemAssetStore(tmp_path)
    generator = FakeImageGenerator()
    resolver = GeneratedAssetResolver(repository=repository, asset_store=store, image_generator=generator)

    first = await resolver.resolve(
        tenant_id=profile.tenant_id,
        revision_id="revision-r4-owned",
        visual_spec=spec,
        content=content,
        design_profile=design,
    )
    second = await resolver.resolve(
        tenant_id=profile.tenant_id,
        revision_id="revision-r4-owned",
        visual_spec=spec,
        content=content,
        design_profile=design,
    )

    requirement_id = spec.asset_requirements[0].requirement_id
    assert generator.calls == 1
    assert first[requirement_id].data == PNG
    assert second[requirement_id].sha256 == hashlib.sha256(PNG).hexdigest()
    persisted = next(iter(repository.source_assets.values()))
    assert await store.verify(persisted.storage_key, persisted.sha256)


def test_renderer_request_binds_owned_image_sha_not_remote_url():
    profile = make_profile()
    design = derive_design_profile(profile)
    content = good_content()
    spec = build_visual_spec(
        visual_spec_id="vs-r4-render",
        revision_id="revision-r4-render",
        content=content,
        design_profile=design,
        generated_visuals_enabled=True,
    )
    requirement = spec.asset_requirements[0]
    sha = hashlib.sha256(PNG).hexdigest()
    resolved = {
        requirement.requirement_id: ResolvedSourceAsset(
            requirement_id=requirement.requirement_id,
            data=PNG,
            content_type="image/png",
            sha256=sha,
            source_asset_id="source-r4",
        )
    }
    request = build_renderer_request(
        revision_id="revision-r4-render",
        visual_spec=spec,
        content=content,
        design_profile=design,
        renderer_name="ChromiumRendererAdapter",
        renderer_version="playwright-1.62.1-chromium-v2-r4",
        resolved_assets=resolved,
    )

    image = next(block for block in request.pages[0].blocks if block.kind == "image")
    assert image.image_sha256 == sha
    assert image.image_data_uri.startswith("data:image/png;base64,")
    assert "http://" not in request.model_dump_json()
    assert "https://" not in request.model_dump_json()
    semantic_digest = request.render_input_digest
    assert semantic_digest == canonical_render_sha256({
        "contract_version": "RendererRequestV1@1",
        "renderer_name": "ChromiumRendererAdapter",
        "renderer_version": "playwright-1.62.1-chromium-v2-r4",
        "revision_id": "revision-r4-render",
        "visual_spec_id": spec.visual_spec_id,
        "visual_spec_digest": request.visual_spec_digest,
        "content_spec_digest": request.content_spec_digest,
        "design_profile_digest": design.digest,
        "visual_pattern": spec.visual_pattern,
        "format": spec.format.value,
        "canvas_width": spec.canvas.width,
        "canvas_height": spec.canvas.height,
        "safe_zone": request.safe_zone.model_dump(mode="json"),
        "theme": request.theme.model_dump(mode="json"),
        "pages": [
            {
                **page.model_dump(mode="json"),
                "blocks": [
                    {key: value for key, value in block.model_dump(mode="json").items() if key != "image_data_uri"}
                    if block.kind == "image" else block.model_dump(mode="json")
                    for block in page.blocks
                ],
            }
            for page in request.pages
        ],
    })
