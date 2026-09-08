from __future__ import annotations

from datetime import datetime, timezone
from inspect import signature

import pytest
from pydantic import ValidationError

from application.visual.design_profile import derive_design_profile
from application.visual.planner import UnsupportedVisualFormat, build_visual_spec
from application.visual.service import VisualAuthorityError, VisualSpecService
from application.visual.validation import VisualSpecValidationError, validate_visual_spec
from domain.profiles.models import (
    AccountType, AgentPolicy, Channel, ClaimPolicy, CopyPolicy, EditorialStrategy,
    Goal, MigrationProvenance, NoveltyPolicy, ProfileIdentity, ProfileVersion,
    PublishingPreferences, VisualSystem, canonical_digest as profile_digest,
)
from domain.production.models import (
    CarouselSlideV1, CarouselSpecV1, ContentRevisionV1, ContentSpecV1,
    GenerationRunState, GenerationRunV1, InfographicSectionV1,
    InfographicSpecV1, RevisionSource, RevisionStatus, SingleImageSpecV1,
    TextFormatSpecV1, canonical_sha256 as production_sha256,
)
from domain.visual.models import TextBlockV1, VisualSpecV1, canonical_visual_sha256


NOW = datetime(2026, 9, 8, 17, 0, tzinfo=timezone.utc)


def make_profile(*, traits=("clean",), tenant_id="tenant-s4") -> ProfileVersion:
    value = ProfileVersion(
        profile_id="profile-s4", tenant_id=tenant_id, version=3,
        identity=ProfileIdentity(name="S4 Golden Profile", account_type=AccountType.NICHE, summary="Golden visual fixture"),
        goals=(Goal.EDUCATE,), audience=("people who value clear technical content",),
        editorial_strategy=EditorialStrategy(topic_families=("technology",)),
        novelty_policy=NoveltyPolicy(),
        copy_policy=CopyPolicy(voice_traits=("clear", "technical"), target_language="es"),
        claim_policy=ClaimPolicy(), visual_system=VisualSystem(traits=tuple(traits)),
        publishing_preferences=PublishingPreferences(channels=(Channel.LINKEDIN, Channel.INSTAGRAM), default_batch_size=4),
        agent_policy=AgentPolicy(), provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW, created_at=NOW, digest="0" * 64,
    )
    return value.model_copy(update={"digest": profile_digest(value)})


def make_single() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-single", plan_id="plan-single", language="es",
        title="Content Seller", hook="Un buen sistema visual no inventa copy.",
        body="El diseño representa contenido ya aceptado.", cta="Guárdalo.",
        alt_text_draft="Pieza editorial con una idea principal.", format="single_image",
        format_spec=SingleImageSpecV1(
            headline="Diseña con referencias, no con copy inventado",
            supporting_copy=("El texto crítico viene del ContentSpec.",), footer="VisualSpec V1",
        ),
    )


def make_carousel() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-carousel", plan_id="plan-carousel", language="es",
        title="Logan automotive", hook="Dos pasos para leer una señal del auto.",
        body="Carrusel de educación automotriz.", cta="Revisa ambos pasos.", format="carousel",
        format_spec=CarouselSpecV1(slides=(
            CarouselSlideV1(slide_id="slide-1", role="hook", headline="Antes de cambiar piezas, observa el síntoma", body="El diagnóstico empieza por evidencia observable."),
            CarouselSlideV1(slide_id="slide-2", role="takeaway", headline="Confirma antes de reemplazar", bullets=("Evita asumir.", "Registra lo observado.")),
        )),
    )


def make_infographic() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-infographic", plan_id="plan-infographic", language="en",
        title="Tech / LinkedIn", hook="A deployment pipeline is a chain of evidence.",
        body="The infographic keeps accepted relationships intact.", format="infographic",
        format_spec=InfographicSpecV1(
            title="From commit to verified release",
            sections=(
                InfographicSectionV1(section_id="commit", label="Commit", value_or_copy="Immutable source identity", relationship="feeds CI"),
                InfographicSectionV1(section_id="ci", label="CI", value_or_copy="Exact-SHA verification", relationship="produces evidence"),
            ),
        ),
    )


def make_text() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-text", plan_id="plan-text", language="es",
        hook="Solo texto.", body="Este formato no requiere VisualSpec en S4.",
        format="text", format_spec=TextFormatSpecV1(),
    )


class FakeProductionRepository:
    def __init__(self, run, revision, content):
        self.runs = {run.run_id: run}
        self.revisions = {revision.revision_id: revision}
        self.artifacts = {content.content_spec_id: {
            "artifact_type": "ContentSpecV1", "artifact_id": content.content_spec_id,
            "digest": production_sha256(content), "payload": content.model_dump(mode="json"),
        }}

    async def get_run(self, tenant_id, run_id):
        run = self.runs.get(run_id)
        return run if run is None or run.tenant_id == tenant_id else None

    async def update_run(self, run):
        self.runs[run.run_id] = run

    async def get_revision(self, tenant_id, revision_id):
        revision = self.revisions.get(revision_id)
        return revision if revision is None or revision.tenant_id == tenant_id else None

    async def get_artifact(self, tenant_id, artifact_id):
        return self.artifacts.get(artifact_id)


class FakeProfileRepository:
    def __init__(self, profile):
        self.profile = profile

    async def get_version(self, profile_id, version):
        return self.profile if (self.profile.profile_id, self.profile.version) == (profile_id, version) else None


class FakeVisualRepository:
    def __init__(self, production):
        self.production = production
        self.design_profiles = {}
        self.visual_specs = {}

    async def save_design_profile(self, profile):
        self.design_profiles.setdefault(profile.design_profile_id, profile)

    async def get_design_profile(self, design_profile_id):
        return self.design_profiles.get(design_profile_id)

    async def save_visual_spec(self, spec):
        assert spec.visual_spec_id not in self.visual_specs
        self.visual_specs[spec.visual_spec_id] = spec

    async def get_visual_spec(self, visual_spec_id):
        return self.visual_specs.get(visual_spec_id)

    async def bind_revision_visual(self, *, revision_id, expected_visual_spec_ref, visual_spec_ref, visual_spec_digest):
        revision = self.production.revisions.get(revision_id)
        if revision is None or revision.visual_spec_ref != expected_visual_spec_ref:
            return None
        updated = revision.model_copy(update={"visual_spec_ref": visual_spec_ref, "visual_spec_digest": visual_spec_digest})
        self.production.revisions[revision_id] = updated
        return updated


def authority_fixture(content):
    profile = make_profile()
    run = GenerationRunV1(
        run_id="run-s4", tenant_id=profile.tenant_id, content_id="content-item-s4",
        profile_id=profile.profile_id, profile_version=profile.version,
        profile_snapshot_digest=profile.digest, plan_id=content.plan_id, plan_digest="b" * 64,
        state=GenerationRunState.VISUAL_PLANNING,
        contract_versions=("ResearchPackV1@1", "ContentSpecV1@1", "EditorialReviewV1@1", "ContentRevisionV1@1"),
        content_spec_ref=content.content_spec_id, started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s4", tenant_id=profile.tenant_id, content_id=run.content_id,
        run_id=run.run_id, source=RevisionSource.GENERATION,
        content_spec_ref=content.content_spec_id, content_spec_digest=production_sha256(content),
        status=RevisionStatus.DRAFT, created_at=NOW,
    )
    production = FakeProductionRepository(run, revision, content)
    visual = FakeVisualRepository(production)
    service = VisualSpecService(
        production_repository=production,
        profile_repository=FakeProfileRepository(profile),
        visual_repository=visual,
    )
    return profile, production, visual, service


def test_design_profile_mapping_is_deterministic_bounded_and_strict():
    profile = make_profile(traits=("clean", "unknown://renderer", "<script>"))
    first = derive_design_profile(profile)
    second = derive_design_profile(profile)
    assert first == second
    assert first.digest == second.digest
    serialized = str(first.model_dump(mode="json"))
    assert "unknown://renderer" not in serialized and "<script>" not in serialized
    with pytest.raises(ValidationError):
        type(first).model_validate({**first.model_dump(mode="json"), "raw_css": "position:fixed"})


def test_unknown_traits_cannot_gain_visual_token_authority():
    clean = derive_design_profile(make_profile(traits=("clean",)))
    noisy = derive_design_profile(make_profile(traits=("clean", "https://evil", "font:url(foo)")))
    assert clean.typography == noisy.typography
    assert clean.palette == noisy.palette
    assert clean.density == noisy.density
    assert clean.layout_family_preferences == noisy.layout_family_preferences
    assert clean.digest != noisy.digest


@pytest.mark.parametrize(("content", "pages"), [(make_single(), 1), (make_carousel(), 2), (make_infographic(), 1)])
def test_three_golden_product_lines_build_valid_renderer_independent_specs(content, pages):
    design = derive_design_profile(make_profile())
    spec = build_visual_spec(visual_spec_id="vs-golden", revision_id="revision-golden", content=content, design_profile=design)
    validate_visual_spec(spec, content=content, design_profile=design)
    assert len(spec.pages) == pages
    assert spec.asset_requirements == ()
    assert (spec.canvas.width, spec.canvas.height) == (1080, 1350)
    assert all(page.layout_family in design.layout_family_preferences for page in spec.pages)


def test_critical_literal_is_rejected_at_contract_boundary():
    with pytest.raises(ValidationError, match="critical text must use copy_ref"):
        TextBlockV1(block_id="bad", literal="invented headline", editorial_critical=True, role="headline")


def test_unknown_copy_ref_fails_closed_even_when_schema_is_structurally_valid():
    content = make_single()
    design = derive_design_profile(make_profile())
    spec = build_visual_spec(visual_spec_id="vs-copy", revision_id="revision-copy", content=content, design_profile=design)
    payload = spec.model_dump(mode="json")
    payload["pages"][0]["blocks"][1]["copy_ref"] = "content_spec.format_spec.not_a_real_field"
    tampered = VisualSpecV1.model_validate(payload)
    with pytest.raises(VisualSpecValidationError, match="unknown copy_ref"):
        validate_visual_spec(tampered, content=content, design_profile=design)


def test_missing_accepted_carousel_copy_is_not_silently_dropped():
    content = make_carousel()
    design = derive_design_profile(make_profile())
    spec = build_visual_spec(visual_spec_id="vs-missing", revision_id="revision-missing", content=content, design_profile=design)
    page = spec.pages[1]
    reduced_page = page.model_copy(update={"blocks": tuple(
        block for block in page.blocks
        if getattr(block, "copy_ref", None) != "content_spec.format_spec.slides[slide-2].bullets[1]"
    )})
    reduced = spec.model_copy(update={"pages": (spec.pages[0], reduced_page)})
    with pytest.raises(VisualSpecValidationError, match="critical visual copy coverage"):
        validate_visual_spec(reduced, content=content, design_profile=design)


def test_text_only_format_stays_outside_s4_visualspec():
    with pytest.raises(UnsupportedVisualFormat):
        build_visual_spec(
            visual_spec_id="vs-text", revision_id="revision-text", content=make_text(),
            design_profile=derive_design_profile(make_profile()),
        )


@pytest.mark.asyncio
async def test_service_binds_exact_lineage_without_crossing_renderer_or_qa_boundary():
    profile, production, visual, service = authority_fixture(make_carousel())
    result = await service.plan_revision(tenant_id=profile.tenant_id, revision_id="revision-s4")
    assert result.run.state == GenerationRunState.VISUAL_PLANNING
    assert result.run.visual_spec_ref == result.visual_spec.visual_spec_id
    assert result.revision.status == RevisionStatus.DRAFT
    assert result.revision.visual_spec_ref == result.visual_spec.visual_spec_id
    assert result.revision.visual_spec_digest == canonical_visual_sha256(result.visual_spec)
    assert result.revision.asset_refs == () and result.revision.qa_report_id is None
    assert result.visual_spec.asset_requirements == ()
    assert result.design_profile.source_profile_digest == profile.digest
    assert "DesignProfileV1@1" in result.run.contract_versions and "VisualSpecV1@1" in result.run.contract_versions
    params = set(signature(VisualSpecService.__init__).parameters)
    assert "renderer" not in params and "asset_store" not in params
    assert len(visual.visual_specs) == 1


@pytest.mark.asyncio
async def test_replanning_appends_visualspec_lineage_instead_of_overwriting_history():
    profile, production, visual, service = authority_fixture(make_single())
    first = await service.plan_revision(tenant_id=profile.tenant_id, revision_id="revision-s4")
    second = await service.plan_revision(tenant_id=profile.tenant_id, revision_id="revision-s4")
    assert second.visual_spec.visual_spec_id != first.visual_spec.visual_spec_id
    assert second.visual_spec.supersedes_visual_spec_id == first.visual_spec.visual_spec_id
    assert len(visual.visual_specs) == 2
    assert production.revisions["revision-s4"].visual_spec_ref == second.visual_spec.visual_spec_id
    assert production.runs["run-s4"].visual_spec_ref == second.visual_spec.visual_spec_id


@pytest.mark.asyncio
async def test_service_fails_closed_on_content_digest_tampering():
    profile, production, _, service = authority_fixture(make_infographic())
    production.artifacts["content-infographic"]["digest"] = "f" * 64
    with pytest.raises(VisualAuthorityError, match="artifact digest mismatch"):
        await service.plan_revision(tenant_id=profile.tenant_id, revision_id="revision-s4")


@pytest.mark.asyncio
async def test_service_fails_closed_when_generation_run_is_past_visual_planning():
    profile, production, _, service = authority_fixture(make_single())
    production.runs["run-s4"] = production.runs["run-s4"].model_copy(update={"state": GenerationRunState.RENDERING})
    with pytest.raises(VisualAuthorityError, match="not in VISUAL_PLANNING"):
        await service.plan_revision(tenant_id=profile.tenant_id, revision_id="revision-s4")
