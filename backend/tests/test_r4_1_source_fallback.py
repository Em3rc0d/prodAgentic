from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from application.rendering import r4_service
from application.rendering.generated_assets import GeneratedAssetResolutionError
from application.rendering.r4_service import R4RenderService, _source_optional_fallback_spec
from domain.production.models import GenerationRunState, RevisionStatus
from domain.visual.models import (
    AssetRequirementKind,
    AssetRequirementV1,
    CanvasV1,
    Density,
    IconLanguage,
    ImageBlockV1,
    ImageTreatment,
    LayoutFamily,
    RenderStrategy,
    SafeZoneV1,
    ShapeBlockV1,
    ShapeKind,
    TextBlockV1,
    VisualFormat,
    VisualPageRole,
    VisualPageV1,
    VisualSpecV1,
    VisualStyleV1,
    canonical_visual_sha256,
)


def _visual_spec() -> VisualSpecV1:
    return VisualSpecV1(
        visual_spec_id="vs-generated",
        content_spec_id="content-spec-1",
        revision_id="revision-1",
        format=VisualFormat.SINGLE_IMAGE,
        canvas=CanvasV1(
            width=1080,
            height=1350,
            safe_zone=SafeZoneV1(
                top=64,
                right=64,
                bottom=64,
                left=64,
            ),
        ),
        render_strategy=RenderStrategy.GENERATED_VISUAL_PLUS_COMPOSITE,
        visual_pattern="single_image.editorial_poster.v2",
        style=VisualStyleV1(
            design_profile_ref="design-1",
            design_profile_digest="d" * 64,
            density=Density.BALANCED,
            image_treatment=ImageTreatment.EDITORIAL_CROP,
            icon_language=IconLanguage.OUTLINE,
        ),
        pages=(
            VisualPageV1(
                page_id="page-0",
                page_index=0,
                role=VisualPageRole.HOOK,
                layout_family=LayoutFamily.EDITORIAL_POSTER,
                blocks=(
                    ShapeBlockV1(
                        block_id="surface",
                        shape=ShapeKind.RECT,
                        token_ref="surface.paper",
                    ),
                    ImageBlockV1(
                        block_id="hero",
                        asset_requirement_ref="hero-generated",
                        treatment=ImageTreatment.EDITORIAL_CROP,
                    ),
                    TextBlockV1(
                        block_id="headline",
                        copy_ref="content_spec.format_spec.headline",
                        role="headline",
                    ),
                ),
            ),
        ),
        asset_requirements=(
            AssetRequirementV1(
                requirement_id="hero-generated",
                kind=AssetRequirementKind.GENERATED_IMAGE,
                purpose="Optional editorial enhancement",
                accepted_content_types=("image/png", "image/jpeg", "image/webp"),
            ),
        ),
    )


def test_source_fallback_supersedes_generated_imagery_without_weakening_copy_authority():
    original = _visual_spec()

    fallback = _source_optional_fallback_spec(original)

    assert fallback.visual_spec_id != original.visual_spec_id
    assert fallback.supersedes_visual_spec_id == original.visual_spec_id
    assert fallback.render_strategy == RenderStrategy.COMPOSED_STATIC
    assert fallback.visual_pattern == "r4.source_fallback.v1"
    assert fallback.asset_requirements == ()
    assert all(
        not isinstance(block, ImageBlockV1)
        for page in fallback.pages
        for block in page.blocks
    )
    assert any(
        isinstance(block, TextBlockV1) and block.copy_ref == "content_spec.format_spec.headline"
        for block in fallback.pages[0].blocks
    )


class _FailingResolver:
    def __init__(self, **kwargs):
        pass

    async def resolve(self, **kwargs):
        raise GeneratedAssetResolutionError(
            "provider unavailable",
            retryable=True,
            fallback_allowed=True,
        )


class _ProductionRepository:
    def __init__(self, revision, run):
        self.revision = revision
        self.run = run
        self.updated = None

    async def get_revision(self, tenant_id, revision_id):
        return self.revision

    async def get_run(self, tenant_id, run_id):
        return self.run

    async def update_run(self, run):
        self.updated = run
        self.run = run


class _VisualRepository:
    def __init__(self, revision):
        self.revision = revision
        self.saved = None

    async def save_visual_spec(self, spec):
        self.saved = spec

    async def bind_revision_visual(
        self,
        *,
        revision_id,
        expected_visual_spec_ref,
        visual_spec_ref,
        visual_spec_digest,
    ):
        assert revision_id == self.revision.revision_id
        assert expected_visual_spec_ref == self.revision.visual_spec_ref
        self.revision = self.revision.model_copy(
            update={
                "visual_spec_ref": visual_spec_ref,
                "visual_spec_digest": visual_spec_digest,
            }
        )
        return self.revision


class _RenderingRepository:
    def __init__(self, run):
        self.run = run
        self.failures = []

    async def claim_run_rendering(self, *, run_id, visual_spec_ref):
        self.run = self.run.model_copy(
            update={"state": GenerationRunState.RENDERING}
        )
        return self.run

    async def get_render_result(self, render_id):
        return SimpleNamespace()

    async def mark_run_failed(self, **kwargs):
        self.failures.append(kwargs)


@pytest.mark.asyncio
async def test_provider_image_failure_degrades_to_certified_composition_in_same_run(monkeypatch):
    visual_spec = _visual_spec()
    revision = SimpleNamespace(
        revision_id="revision-1",
        run_id="run-1",
        content_id="content-1",
        tenant_id="tenant-1",
        status=RevisionStatus.DRAFT,
        qa_report_id=None,
        visual_spec_ref=visual_spec.visual_spec_id,
        visual_spec_digest=canonical_visual_sha256(visual_spec),
        content_spec_ref="content-spec-1",
        content_spec_digest="c" * 64,
        asset_refs=(),
        model_copy=lambda update: None,
    )

    # Use a tiny immutable object with model_copy semantics for repository CAS.
    class Revision:
        def __init__(self, **values):
            self.__dict__.update(values)

        def model_copy(self, *, update):
            values = dict(self.__dict__)
            values.pop("model_copy", None)
            values.update(update)
            return Revision(**values)

    revision = Revision(
        revision_id="revision-1",
        run_id="run-1",
        content_id="content-1",
        tenant_id="tenant-1",
        status=RevisionStatus.DRAFT,
        qa_report_id=None,
        visual_spec_ref=visual_spec.visual_spec_id,
        visual_spec_digest=canonical_visual_sha256(visual_spec),
        content_spec_ref="content-spec-1",
        content_spec_digest="c" * 64,
        asset_refs=(),
    )

    class Run:
        def __init__(self, **values):
            self.__dict__.update(values)

        def model_copy(self, *, update):
            values = dict(self.__dict__)
            values.update(update)
            return Run(**values)

    run = Run(
        run_id="run-1",
        tenant_id="tenant-1",
        content_id="content-1",
        visual_spec_ref=visual_spec.visual_spec_id,
        content_spec_ref="content-spec-1",
        state=GenerationRunState.VISUAL_PLANNING,
        failure=None,
        completed_at=None,
    )

    production = _ProductionRepository(revision, run)
    visual = _VisualRepository(revision)
    rendering = _RenderingRepository(run)

    service = R4RenderService(
        production_repository=production,
        visual_repository=visual,
        rendering_repository=rendering,
        renderer=SimpleNamespace(name="renderer", version="v4"),
        asset_store=SimpleNamespace(),
        image_generator=SimpleNamespace(),
    )

    content = SimpleNamespace()
    design = SimpleNamespace()
    service._load_content = AsyncMock(return_value=content)
    service._load_visual_spec = AsyncMock(return_value=visual_spec)
    service._load_design_profile = AsyncMock(return_value=design)
    service._verify_result = AsyncMock(return_value=None)
    service._bind_or_verify_revision = AsyncMock(side_effect=lambda **kwargs: kwargs["revision"])
    service._finish_or_verify_run = AsyncMock(side_effect=lambda **kwargs: kwargs["run"])

    monkeypatch.setattr(r4_service, "validate_visual_spec", lambda *args, **kwargs: None)
    monkeypatch.setattr(r4_service, "GeneratedAssetResolver", _FailingResolver)
    monkeypatch.setattr(
        r4_service,
        "build_renderer_request",
        lambda **kwargs: SimpleNamespace(render_id="render-fallback"),
    )

    result = await service.render_revision(
        tenant_id="tenant-1",
        revision_id="revision-1",
    )

    assert rendering.failures == []
    assert visual.saved is not None
    assert visual.saved.asset_requirements == ()
    assert production.updated is not None
    assert production.updated.visual_spec_ref == visual.saved.visual_spec_id
    assert result.visual_spec.visual_spec_id == visual.saved.visual_spec_id
