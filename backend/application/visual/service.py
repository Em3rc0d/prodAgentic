from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from application.visual.design_profile import derive_design_profile
from application.visual.planner import UnsupportedVisualFormat, build_visual_spec
from application.visual.validation import VisualSpecValidationError, validate_visual_spec
from domain.production.models import (
    ContentRevisionV1,
    ContentSpecV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionStatus,
    canonical_sha256 as production_sha256,
)
from domain.visual.models import DesignProfileV1, VisualSpecV1, canonical_visual_sha256
from domain.visual.ports import ProfileVersionReaderPort, VisualProductionAuthorityPort, VisualRepositoryPort


class VisualAuthorityError(RuntimeError):
    pass


class VisualPlanningConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualPlanningResult:
    run: GenerationRunV1
    revision: ContentRevisionV1
    content: ContentSpecV1
    design_profile: DesignProfileV1
    visual_spec: VisualSpecV1
    visual_spec_digest: str


class VisualSpecService:
    """S4 authority: frozen text revision -> typed VisualSpec only.

    There is deliberately no renderer or asset-store dependency here. S4
    persists visual intent, binds lineage and leaves the GenerationRun in
    VISUAL_PLANNING for S5 to start render execution.
    """

    contract_versions = ("DesignProfileV1@1", "VisualSpecV1@1")

    def __init__(self, *, production_repository: VisualProductionAuthorityPort, profile_repository: ProfileVersionReaderPort, visual_repository: VisualRepositoryPort):
        self.production_repository = production_repository
        self.profile_repository = profile_repository
        self.visual_repository = visual_repository

    async def plan_revision(self, *, tenant_id: str, revision_id: str) -> VisualPlanningResult:
        revision = await self.production_repository.get_revision(tenant_id, revision_id)
        if revision is None:
            raise VisualAuthorityError("ContentRevision not found")
        if revision.tenant_id != tenant_id:
            raise VisualAuthorityError("ContentRevision tenant authority mismatch")
        if revision.status != RevisionStatus.DRAFT:
            raise VisualAuthorityError("Visual planning requires a DRAFT ContentRevision")
        if revision.asset_refs or revision.qa_report_id is not None:
            raise VisualAuthorityError("S4 cannot plan a revision that already owns render/QA state")

        run = await self.production_repository.get_run(tenant_id, revision.run_id)
        if run is None:
            raise VisualAuthorityError("GenerationRun not found")
        if run.tenant_id != tenant_id or run.content_id != revision.content_id:
            raise VisualAuthorityError("GenerationRun/ContentRevision authority mismatch")
        if run.state != GenerationRunState.VISUAL_PLANNING:
            raise VisualAuthorityError("GenerationRun is not in VISUAL_PLANNING")
        if run.content_spec_ref != revision.content_spec_ref:
            raise VisualAuthorityError("GenerationRun/ContentRevision ContentSpec mismatch")

        artifact = await self.production_repository.get_artifact(tenant_id, revision.content_spec_ref)
        if artifact is None:
            raise VisualAuthorityError("ContentSpec artifact is unavailable")
        if artifact.get("artifact_type") != "ContentSpecV1":
            raise VisualAuthorityError("revision does not reference a ContentSpecV1 artifact")
        try:
            content = ContentSpecV1.model_validate(artifact.get("payload"))
        except Exception as exc:
            raise VisualAuthorityError("persisted ContentSpecV1 payload is invalid") from exc

        content_digest = production_sha256(content)
        if content.content_spec_id != revision.content_spec_ref:
            raise VisualAuthorityError("ContentSpec identity mismatch")
        if content_digest != revision.content_spec_digest:
            raise VisualAuthorityError("ContentRevision ContentSpec digest mismatch")
        if artifact.get("digest") != content_digest:
            raise VisualAuthorityError("persisted ContentSpec artifact digest mismatch")

        profile = await self.profile_repository.get_version(run.profile_id, run.profile_version)
        if profile is None:
            raise VisualAuthorityError("frozen ProfileVersion is unavailable")
        if profile.tenant_id != tenant_id:
            raise VisualAuthorityError("ProfileVersion tenant authority mismatch")
        if profile.digest != run.profile_snapshot_digest:
            raise VisualAuthorityError("GenerationRun/ProfileVersion digest mismatch")

        design_profile = derive_design_profile(profile)
        await self.visual_repository.save_design_profile(design_profile)

        previous_visual_spec_id = revision.visual_spec_ref
        if previous_visual_spec_id is not None:
            previous = await self.visual_repository.get_visual_spec(previous_visual_spec_id)
            if previous is None:
                raise VisualAuthorityError("current revision VisualSpec lineage is unavailable")
            if previous.revision_id != revision.revision_id or previous.content_spec_id != content.content_spec_id:
                raise VisualAuthorityError("current revision VisualSpec lineage is inconsistent")
            if run.visual_spec_ref != previous_visual_spec_id:
                run = run.model_copy(update={"visual_spec_ref": previous_visual_spec_id})
                await self.production_repository.update_run(run)
        elif run.visual_spec_ref is not None:
            raise VisualAuthorityError("GenerationRun has an unbound VisualSpec reference")

        try:
            visual_spec = build_visual_spec(
                visual_spec_id=f"vs-{uuid4().hex}",
                revision_id=revision.revision_id,
                content=content,
                design_profile=design_profile,
                supersedes_visual_spec_id=previous_visual_spec_id,
            )
            validate_visual_spec(visual_spec, content=content, design_profile=design_profile)
        except UnsupportedVisualFormat:
            raise
        except VisualSpecValidationError:
            raise
        except Exception as exc:
            raise VisualSpecValidationError("VisualSpec construction failed closed") from exc

        visual_spec_digest = canonical_visual_sha256(visual_spec)
        await self.visual_repository.save_visual_spec(visual_spec)
        bound_revision = await self.visual_repository.bind_revision_visual(
            revision_id=revision.revision_id,
            expected_visual_spec_ref=previous_visual_spec_id,
            visual_spec_ref=visual_spec.visual_spec_id,
            visual_spec_digest=visual_spec_digest,
        )
        if bound_revision is None:
            raise VisualPlanningConflict(
                "ContentRevision visual pointer changed during planning; immutable spec was retained as lineage"
            )

        versions = list(run.contract_versions)
        for contract in self.contract_versions:
            if contract not in versions:
                versions.append(contract)
        updated_run = run.model_copy(
            update={
                "visual_spec_ref": visual_spec.visual_spec_id,
                "contract_versions": tuple(versions),
            }
        )
        await self.production_repository.update_run(updated_run)

        return VisualPlanningResult(
            run=updated_run,
            revision=bound_revision,
            content=content,
            design_profile=design_profile,
            visual_spec=visual_spec,
            visual_spec_digest=visual_spec_digest,
        )
