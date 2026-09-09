from __future__ import annotations

import hashlib
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from application.rendering.copy_resolver import UnsupportedRenderInput, build_renderer_request
from application.rendering.service import RenderExecutionFailed, RenderService
from application.visual.design_profile import derive_design_profile
from application.visual.planner import build_visual_spec
from domain.profiles.models import (
    AccountType, AgentPolicy, Channel, ClaimPolicy, CopyPolicy, EditorialStrategy,
    Goal, MigrationProvenance, NoveltyPolicy, ProfileIdentity, ProfileVersion,
    PublishingPreferences, VisualSystem, canonical_digest as profile_digest,
)
from domain.production.models import (
    CarouselSlideV1, CarouselSpecV1, ContentRevisionV1, ContentSpecV1,
    GenerationFailureV1, GenerationRunState, GenerationRunV1,
    InfographicSectionV1, InfographicSpecV1, RevisionSource, RevisionStatus,
    SingleImageSpecV1, canonical_sha256 as production_sha256,
)
from domain.rendering.models import AssetV1, RendererRequestV1, canonical_render_sha256
from domain.rendering.ports import RenderedPageBytes, RendererPortError
from domain.visual.models import RenderStrategy, canonical_visual_sha256
from infrastructure.assets.filesystem import FilesystemAssetStore


NOW = datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc)


def make_profile(*, traits=("clean", "technical")) -> ProfileVersion:
    provisional = ProfileVersion(
        profile_id="profile-s5", tenant_id="tenant-s5", version=1,
        identity=ProfileIdentity(name="S5 Golden Profile", account_type=AccountType.NICHE, summary="Renderer fixture"),
        goals=(Goal.EDUCATE,), audience=("people who value clear visual explanations",),
        editorial_strategy=EditorialStrategy(topic_families=("systems",)), novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("clear", "technical"), target_language="es"), claim_policy=ClaimPolicy(),
        visual_system=VisualSystem(traits=tuple(traits)),
        publishing_preferences=PublishingPreferences(channels=(Channel.LINKEDIN,), default_batch_size=4),
        agent_policy=AgentPolicy(), provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW, created_at=NOW, digest="0" * 64,
    )
    return provisional.model_copy(update={"digest": profile_digest(provisional)})


def make_single() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-seller", plan_id="plan-seller", language="es",
        title="Content Seller", hook="El copy crítico no se improvisa.", body="La pieza visual respeta el contenido aceptado.",
        cta="Guárdalo.", alt_text_draft="Tarjeta editorial sobre copy y diseño.", format="single_image",
        format_spec=SingleImageSpecV1(
            headline="Diseña con referencias, no con copy inventado",
            supporting_copy=("El texto crítico viene del ContentSpec.", "El renderer solo compone."),
            footer="prodAgentic · S5",
        ),
    )


def make_carousel() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="logan-carousel", plan_id="plan-logan", language="es",
        title="Logan automotive", hook="Primero observa. Luego confirma.", body="Educación automotriz sin asumir diagnósticos.",
        cta="Revisa ambas señales.", alt_text_draft="Carrusel de dos páginas sobre diagnóstico responsable.", format="carousel",
        format_spec=CarouselSpecV1(slides=(
            CarouselSlideV1(slide_id="slide-1", role="hook", headline="Antes de cambiar piezas, observa el síntoma", body="El diagnóstico empieza por evidencia observable."),
            CarouselSlideV1(slide_id="slide-2", role="takeaway", headline="Confirma antes de reemplazar", bullets=("Evita asumir.", "Registra lo observado.")),
        )),
    )


def make_infographic() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="tech-infographic", plan_id="plan-tech", language="en",
        title="Tech / LinkedIn", hook="A deployment pipeline is a chain of evidence.", body="Exact-SHA evidence keeps the chain inspectable.",
        alt_text_draft="Infographic showing commit and CI evidence flow.", format="infographic",
        format_spec=InfographicSpecV1(
            title="From commit to verified release",
            sections=(
                InfographicSectionV1(section_id="commit", label="Commit", value_or_copy="Immutable source identity", relationship="feeds CI"),
                InfographicSectionV1(section_id="ci", label="CI", value_or_copy="Exact-SHA verification", relationship="produces evidence"),
            ),
        ),
    )


def make_authority(content: ContentSpecV1):
    profile = make_profile()
    design = derive_design_profile(profile)
    revision_id = "revision-s5"
    spec = build_visual_spec(
        visual_spec_id="visual-s5", revision_id=revision_id, content=content, design_profile=design,
    )
    run = GenerationRunV1(
        run_id="run-s5", tenant_id=profile.tenant_id, content_id="content-item-s5",
        profile_id=profile.profile_id, profile_version=profile.version, profile_snapshot_digest=profile.digest,
        plan_id=content.plan_id, plan_digest="b" * 64, state=GenerationRunState.VISUAL_PLANNING,
        contract_versions=("ContentSpecV1@1", "ContentRevisionV1@1", "DesignProfileV1@1", "VisualSpecV1@1"),
        content_spec_ref=content.content_spec_id, visual_spec_ref=spec.visual_spec_id, started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id=revision_id, tenant_id=profile.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=content.content_spec_id,
        content_spec_digest=production_sha256(content), visual_spec_ref=spec.visual_spec_id,
        visual_spec_digest=canonical_visual_sha256(spec), status=RevisionStatus.DRAFT, created_at=NOW,
    )
    return profile, content, design, spec, run, revision


@pytest.mark.parametrize("content", [make_single(), make_carousel(), make_infographic()])
def test_renderer_request_resolves_exact_critical_copy_and_is_deterministic(content):
    _, content, design, spec, _, revision = make_authority(content)
    first = build_renderer_request(
        revision_id=revision.revision_id, visual_spec=spec, content=content, design_profile=design,
        renderer_name="ChromiumRendererAdapter", renderer_version="playwright-1.62.1-chromium-v1",
    )
    second = build_renderer_request(
        revision_id=revision.revision_id, visual_spec=spec, content=content, design_profile=design,
        renderer_name="ChromiumRendererAdapter", renderer_version="playwright-1.62.1-chromium-v1",
    )
    assert first == second
    assert first.render_id == f"render-{first.render_input_digest}"
    resolved = "\n".join(
        block.text or "\n".join(block.items)
        for page in first.pages for block in page.blocks if block.text or block.items
    )
    for page in spec.pages:
        for block in page.blocks:
            ref = getattr(block, "copy_ref", None)
            if ref:
                from application.visual.validation import resolve_copy_ref
                assert resolve_copy_ref(content, ref) in resolved


def test_renderer_request_rejects_external_image_strategy_before_side_effects():
    _, content, design, spec, _, revision = make_authority(make_single())
    unsupported = spec.model_copy(update={"render_strategy": RenderStrategy.GENERATED_BACKGROUND})
    with pytest.raises(UnsupportedRenderInput, match="not certified"):
        build_renderer_request(
            revision_id=revision.revision_id, visual_spec=unsupported, content=content, design_profile=design,
            renderer_name="ChromiumRendererAdapter", renderer_version="playwright-1.62.1-chromium-v1",
        )


def test_renderer_request_contract_is_strict():
    _, content, design, spec, _, revision = make_authority(make_single())
    request = build_renderer_request(
        revision_id=revision.revision_id, visual_spec=spec, content=content, design_profile=design,
        renderer_name="ChromiumRendererAdapter", renderer_version="playwright-1.62.1-chromium-v1",
    )
    with pytest.raises(ValidationError):
        RendererRequestV1.model_validate({**request.model_dump(mode="json"), "freeform_css": "position:fixed"})


@pytest.mark.asyncio
async def test_filesystem_asset_store_owns_bytes_hashes_and_survives_restart(tmp_path: Path):
    store = FilesystemAssetStore(tmp_path)
    data = b"abc"
    stored = await store.put(
        data, tenant_id="tenant-a", revision_id="revision-a", render_id="render-a",
        page_index=0, content_type="image/png",
    )
    assert stored.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert stored.storage_key.startswith("renders/") and "tenant-a" not in stored.storage_key
    assert await store.get(stored.storage_key) == data
    assert await store.verify(stored.storage_key, stored.sha256)

    reopened = FilesystemAssetStore(tmp_path)
    assert await reopened.get(stored.storage_key) == data
    assert await reopened.verify(stored.storage_key, stored.sha256)


@pytest.mark.asyncio
async def test_filesystem_asset_store_rejects_traversal_and_symlink_escape(tmp_path: Path):
    store = FilesystemAssetStore(tmp_path / "root")
    with pytest.raises(Exception, match="traversal"):
        await store.get("renders/../outside.png")

    outside = tmp_path / "outside"
    outside.mkdir()
    link = store.root / "renders" / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this test filesystem")
    with pytest.raises(Exception, match="symlink"):
        await store.get("renders/link/file.png")


def _fake_png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)


class FakeProductionRepository:
    def __init__(self, run, revision, content):
        self.run = run
        self.revision = revision
        self.artifact = {
            "artifact_type": "ContentSpecV1", "artifact_id": content.content_spec_id,
            "digest": production_sha256(content), "payload": content.model_dump(mode="json"),
        }

    async def get_run(self, tenant_id, run_id):
        return self.run if self.run.tenant_id == tenant_id and self.run.run_id == run_id else None

    async def update_run(self, run):
        self.run = run

    async def get_revision(self, tenant_id, revision_id):
        return self.revision if self.revision.tenant_id == tenant_id and self.revision.revision_id == revision_id else None

    async def get_artifact(self, tenant_id, artifact_id):
        return self.artifact if tenant_id == self.run.tenant_id and artifact_id == self.artifact["artifact_id"] else None


class FakeVisualRepository:
    def __init__(self, spec, design):
        self.spec = spec
        self.design = design

    async def get_visual_spec(self, visual_spec_id):
        return self.spec if self.spec.visual_spec_id == visual_spec_id else None

    async def get_design_profile(self, design_profile_id):
        return self.design if self.design.design_profile_id == design_profile_id else None


class FakeRenderingRepository:
    def __init__(self, production):
        self.production = production
        self.assets = {}
        self.results = {}

    async def get_asset(self, asset_id):
        return self.assets.get(asset_id)

    async def save_asset(self, asset):
        existing = self.assets.get(asset.asset_id)
        if existing is not None and existing != asset:
            raise ValueError("asset collision")
        self.assets[asset.asset_id] = asset

    async def get_render_result(self, render_id):
        return self.results.get(render_id)

    async def save_render_result(self, result):
        existing = self.results.get(result.render_id)
        if existing is not None and existing != result:
            raise ValueError("result collision")
        self.results[result.render_id] = result

    async def claim_run_rendering(self, *, run_id, visual_spec_ref):
        run = self.production.run
        if run.run_id != run_id or run.visual_spec_ref != visual_spec_ref:
            return None
        if run.state == GenerationRunState.VISUAL_PLANNING:
            contracts = tuple(dict.fromkeys((*run.contract_versions, "RendererRequestV1@1", "AssetV1@1", "RenderResultV1@1")))
            self.production.run = run.model_copy(update={"state": GenerationRunState.RENDERING, "contract_versions": contracts})
        return self.production.run if self.production.run.state in {GenerationRunState.RENDERING, GenerationRunState.QA} else None

    async def finish_run_qa(self, *, run_id, visual_spec_ref):
        run = self.production.run
        if run.run_id == run_id and run.visual_spec_ref == visual_spec_ref and run.state == GenerationRunState.RENDERING:
            self.production.run = run.model_copy(update={"state": GenerationRunState.QA, "failure": None})
        return self.production.run if self.production.run.state == GenerationRunState.QA else None

    async def mark_run_failed(self, *, run_id, visual_spec_ref, failure):
        run = self.production.run
        if run.run_id == run_id and run.visual_spec_ref == visual_spec_ref and run.state == GenerationRunState.RENDERING:
            self.production.run = run.model_copy(update={"state": GenerationRunState.FAILED, "failure": failure, "completed_at": NOW})
        return self.production.run

    async def bind_revision_assets(self, *, revision_id, visual_spec_ref, visual_spec_digest, expected_asset_refs, asset_refs):
        revision = self.production.revision
        if (
            revision.revision_id != revision_id or revision.status != RevisionStatus.DRAFT
            or revision.visual_spec_ref != visual_spec_ref or revision.visual_spec_digest != visual_spec_digest
            or revision.asset_refs != expected_asset_refs
        ):
            return None
        self.production.revision = revision.model_copy(update={"asset_refs": asset_refs, "status": RevisionStatus.QA_PENDING})
        return self.production.revision


class FakeRenderer:
    name = "ChromiumRendererAdapter"
    version = "playwright-1.62.1-chromium-v1"

    def __init__(self, *, fail=False, wrong_dimensions=False):
        self.fail = fail
        self.wrong_dimensions = wrong_dimensions
        self.calls = 0

    async def render(self, request):
        self.calls += 1
        if self.fail:
            raise RendererPortError("temporary renderer outage", retryable=True)
        pages = []
        for page in request.pages:
            width = request.canvas_width + (1 if self.wrong_dimensions else 0)
            pages.append(RenderedPageBytes(
                page_id=page.page_id, page_index=page.page_index,
                width=width, height=request.canvas_height, content_type="image/png",
                data=_fake_png(width, request.canvas_height),
            ))
        return tuple(pages)


@pytest.mark.asyncio
async def test_render_service_attaches_complete_owned_set_and_stops_at_qa_pending(tmp_path: Path):
    profile, content, design, spec, run, revision = make_authority(make_carousel())
    production = FakeProductionRepository(run, revision, content)
    rendering = FakeRenderingRepository(production)
    renderer = FakeRenderer()
    service = RenderService(
        production_repository=production, visual_repository=FakeVisualRepository(spec, design),
        rendering_repository=rendering, renderer=renderer, asset_store=FilesystemAssetStore(tmp_path),
    )
    result = await service.render_revision(tenant_id=profile.tenant_id, revision_id=revision.revision_id)
    assert result.run.state == GenerationRunState.QA
    assert result.revision.status == RevisionStatus.QA_PENDING
    assert result.revision.qa_report_id is None
    assert len(result.revision.asset_refs) == len(spec.pages) == 2
    assert len(result.render_result.assets) == 2
    assert all(asset.width == 1080 and asset.height == 1350 for asset in result.render_result.assets)
    assert all([await service.asset_store.verify(asset.storage_key, asset.sha256) for asset in result.render_result.assets])
    assert "RendererRequestV1@1" in result.run.contract_versions

    # Retry/restart semantics reuse the immutable result and bytes instead of rendering again.
    recovered = RenderService(
        production_repository=production, visual_repository=FakeVisualRepository(spec, design),
        rendering_repository=rendering, renderer=renderer, asset_store=FilesystemAssetStore(tmp_path),
    )
    second = await recovered.render_revision(tenant_id=profile.tenant_id, revision_id=revision.revision_id)
    assert second.render_result == result.render_result
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_render_service_rejects_dimension_mismatch_without_binding_partial_assets(tmp_path: Path):
    profile, content, design, spec, run, revision = make_authority(make_single())
    production = FakeProductionRepository(run, revision, content)
    rendering = FakeRenderingRepository(production)
    service = RenderService(
        production_repository=production, visual_repository=FakeVisualRepository(spec, design),
        rendering_repository=rendering, renderer=FakeRenderer(wrong_dimensions=True), asset_store=FilesystemAssetStore(tmp_path),
    )
    with pytest.raises(RenderExecutionFailed):
        await service.render_revision(tenant_id=profile.tenant_id, revision_id=revision.revision_id)
    assert production.revision.status == RevisionStatus.DRAFT
    assert production.revision.asset_refs == ()
    assert production.run.state == GenerationRunState.FAILED


@pytest.mark.asyncio
async def test_render_service_renderer_failure_preserves_text_and_visual_authority(tmp_path: Path):
    profile, content, design, spec, run, revision = make_authority(make_infographic())
    production = FakeProductionRepository(run, revision, content)
    rendering = FakeRenderingRepository(production)
    service = RenderService(
        production_repository=production, visual_repository=FakeVisualRepository(spec, design),
        rendering_repository=rendering, renderer=FakeRenderer(fail=True), asset_store=FilesystemAssetStore(tmp_path),
    )
    with pytest.raises(RenderExecutionFailed):
        await service.render_revision(tenant_id=profile.tenant_id, revision_id=revision.revision_id)
    assert production.revision.content_spec_ref == content.content_spec_id
    assert production.revision.content_spec_digest == production_sha256(content)
    assert production.revision.visual_spec_ref == spec.visual_spec_id
    assert production.revision.visual_spec_digest == canonical_visual_sha256(spec)
    assert production.revision.asset_refs == () and production.revision.status == RevisionStatus.DRAFT
    assert production.run.failure is not None
    assert production.run.failure.code == "S5_RENDERER_EXECUTION_FAILED"
