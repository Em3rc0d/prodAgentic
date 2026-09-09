from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from domain.approval.models import (
    ApprovalAssetV2,
    ApprovalBundleV2,
    ReviewAuthoritySnapshotV1,
    canonical_approval_sha256,
)
from domain.approval.ports import ApprovalRepositoryPort
from domain.planning.models import ContentEditorialState
from domain.production.models import (
    ClaimPublishability,
    ContentRevisionV1,
    ContentSpecV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
    canonical_sha256 as production_sha256,
    utc_now,
)
from domain.quality.models import QAVerdict
from domain.rendering.ports import AssetStorePort, RenderingRepositoryPort
from domain.visual.models import TextBlockV1, VisualSpecV1, canonical_visual_sha256
from domain.visual.ports import VisualRepositoryPort


class ApprovalAuthorityError(RuntimeError):
    pass


class ApprovalConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class HumanEditResult:
    revision: ContentRevisionV1
    run: GenerationRunV1
    visual_reused: bool
    invalidated: tuple[str, ...]


class ApprovalService:
    """S7 authority: exact human Review -> immutable ApprovalBundleV2.

    Approval never mutates ContentRevision. Human edits fork new lineage instead.
    Publishing/scheduling are intentionally outside this service.
    """

    def __init__(
        self,
        *,
        planning_repository,
        profile_repository,
        production_repository,
        visual_repository: VisualRepositoryPort,
        rendering_repository: RenderingRepositoryPort,
        quality_repository,
        approval_repository: ApprovalRepositoryPort,
        asset_store: AssetStorePort,
    ):
        self.planning = planning_repository
        self.profiles = profile_repository
        self.production = production_repository
        self.visual = visual_repository
        self.rendering = rendering_repository
        self.quality = quality_repository
        self.approvals = approval_repository
        self.asset_store = asset_store

    async def review_snapshot(self, *, tenant_id: str, revision_id: str) -> ReviewAuthoritySnapshotV1:
        revision = await self.production.get_revision(tenant_id, revision_id)
        if revision is None:
            raise ApprovalAuthorityError("ContentRevision not found")
        if revision.status != RevisionStatus.REVIEWABLE:
            raise ApprovalAuthorityError("Approval requires a REVIEWABLE revision")
        if revision.qa_report_id is None:
            raise ApprovalAuthorityError("REVIEWABLE revision is missing QA authority")

        item = await self.planning.get_content_item(revision.content_id)
        if item is None or item.tenant_id != tenant_id:
            raise ApprovalAuthorityError("ContentItem authority is unavailable")
        if item.current_revision_id != revision_id:
            raise ApprovalConflict("Review snapshot is stale: ContentItem points to another revision")

        run = await self.production.get_run(tenant_id, revision.run_id)
        if run is None or run.content_id != revision.content_id:
            raise ApprovalAuthorityError("GenerationRun/ContentRevision authority mismatch")
        if run.state != GenerationRunState.COMPLETED:
            raise ApprovalAuthorityError("Approval requires completed S6 lineage")
        if run.content_spec_ref != revision.content_spec_ref:
            raise ApprovalAuthorityError("GenerationRun ContentSpec reference differs from revision")

        profile = await self.profiles.get_version(run.profile_id, run.profile_version)
        if profile is None or profile.tenant_id != tenant_id or profile.digest != run.profile_snapshot_digest:
            raise ApprovalAuthorityError("Frozen ProfileVersion authority mismatch")

        if run.research_pack_ref is None:
            raise ApprovalAuthorityError("ResearchPack authority is unavailable")
        research_record = await self.production.get_artifact(tenant_id, run.research_pack_ref)
        content_record = await self.production.get_artifact(tenant_id, revision.content_spec_ref)
        if research_record is None or content_record is None:
            raise ApprovalAuthorityError("Production authority artifacts are unavailable")
        research_digest = research_record.get("digest")
        if not isinstance(research_digest, str) or len(research_digest) != 64:
            raise ApprovalAuthorityError("ResearchPack digest is unavailable")
        if content_record.get("digest") != revision.content_spec_digest:
            raise ApprovalAuthorityError("ContentSpec persisted digest mismatch")
        content = ContentSpecV1.model_validate(content_record.get("payload"))
        if production_sha256(content) != revision.content_spec_digest:
            raise ApprovalAuthorityError("ContentSpec canonical digest mismatch")

        visual_digest = None
        if revision.visual_spec_ref is not None:
            spec = await self.visual.get_visual_spec(revision.visual_spec_ref)
            if spec is None or spec.revision_id != revision_id:
                raise ApprovalAuthorityError("VisualSpec authority is unavailable")
            visual_digest = canonical_visual_sha256(spec)
            if visual_digest != revision.visual_spec_digest:
                raise ApprovalAuthorityError("VisualSpec digest mismatch")
        elif revision.visual_spec_digest is not None:
            raise ApprovalAuthorityError("VisualSpec digest exists without VisualSpec reference")

        report = await self.quality.get_report(tenant_id, revision.qa_report_id)
        if report is None or report.revision_id != revision_id:
            raise ApprovalAuthorityError("QAReport authority is unavailable")
        if report.verdict == QAVerdict.FAIL:
            raise ApprovalAuthorityError("Failing QAReport cannot cross Approval boundary")
        if report.content_spec_digest != revision.content_spec_digest:
            raise ApprovalAuthorityError("QAReport ContentSpec digest mismatch")

        approval_assets: list[ApprovalAssetV2] = []
        actual_digests: list[str] = []
        for asset_id in revision.asset_refs:
            asset = await self.rendering.get_asset(asset_id)
            if asset is None or asset.tenant_id != tenant_id or asset.revision_id != revision_id:
                raise ApprovalAuthorityError("AssetV1 lineage mismatch")
            try:
                data = await self.asset_store.get(asset.storage_key)
            except Exception as exc:
                raise ApprovalAuthorityError("Approved asset bytes are unavailable") from exc
            actual_sha = hashlib.sha256(data).hexdigest()
            if len(data) != asset.byte_size or actual_sha != asset.sha256:
                raise ApprovalAuthorityError("Approved asset bytes/hash changed after QA")
            approval_assets.append(ApprovalAssetV2(asset_id=asset.asset_id, sha256=actual_sha))
            actual_digests.append(actual_sha)

        if tuple(actual_digests) != report.asset_digests:
            raise ApprovalAuthorityError("QAReport asset digests differ from owned bytes")

        existing = await self.approvals.get_by_revision(tenant_id, revision_id)
        bound = {
            "tenant_id": tenant_id,
            "content_id": revision.content_id,
            "revision_id": revision_id,
            "profile_snapshot_digest": run.profile_snapshot_digest,
            "plan_digest": run.plan_digest,
            "research_digest": research_digest,
            "content_digest": revision.content_spec_digest,
            "visual_spec_digest": visual_digest,
            "assets": [asset.model_dump(mode="json") for asset in approval_assets],
            "qa_digest": report.digest,
            "policy_version": report.policy_version,
        }
        review_digest = canonical_approval_sha256(bound)
        approval_available = (
            existing is None
            and item.editorial_state
            in {ContentEditorialState.PRODUCING, ContentEditorialState.READY_FOR_REVIEW}
        )

        return ReviewAuthoritySnapshotV1(
            tenant_id=tenant_id,
            content_id=revision.content_id,
            revision_id=revision_id,
            review_digest=review_digest,
            revision_status="REVIEWABLE",
            editorial_state=item.editorial_state.value,
            approval_available=approval_available,
            existing_approval_id=existing.approval_id if existing else item.latest_approval_id,
            profile_snapshot_digest=run.profile_snapshot_digest,
            plan_digest=run.plan_digest,
            research_digest=research_digest,
            content_digest=revision.content_spec_digest,
            visual_spec_digest=visual_digest,
            qa_digest=report.digest,
            asset_digests=tuple(actual_digests),
            content=content.model_dump(mode="json"),
        )

    async def approve(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        expected_review_digest: str,
        approved_by: str,
        now: datetime | None = None,
    ) -> ApprovalBundleV2:
        snapshot = await self.review_snapshot(tenant_id=tenant_id, revision_id=revision_id)
        if snapshot.review_digest != expected_review_digest:
            raise ApprovalConflict("Review authority changed; refresh before approving")

        clock = now or utc_now()
        existing = await self.approvals.get_by_revision(tenant_id, revision_id)
        if existing is not None:
            # Crash recovery boundary: an immutable bundle can already exist while the
            # mutable ContentItem pointer still says READY_FOR_REVIEW. Replaying the same
            # exact review must finish that CAS rather than fabricate a second approval.
            ready = await self.approvals.ensure_ready_for_review(
                content_id=existing.content_id,
                revision_id=existing.revision_id,
                now=clock,
            )
            if not ready:
                raise ApprovalConflict("ContentItem changed before durable Approval recovery")
            bound = await self.approvals.bind_approval(
                content_id=existing.content_id,
                revision_id=existing.revision_id,
                approval_id=existing.approval_id,
                now=clock,
            )
            if not bound:
                raise ApprovalConflict("ContentItem changed before durable Approval recovery")
            return existing
        if not snapshot.approval_available:
            raise ApprovalConflict("Revision is not currently available for approval")

        ready = await self.approvals.ensure_ready_for_review(
            content_id=snapshot.content_id,
            revision_id=revision_id,
            now=clock,
        )
        if not ready:
            raise ApprovalConflict("ContentItem changed before approval could be claimed")

        # Re-read every bound authority after the lifecycle mirror. This blocks a
        # concurrent edit/current_revision pointer change between Review and Approve.
        refreshed = await self.review_snapshot(tenant_id=tenant_id, revision_id=revision_id)
        if refreshed.review_digest != expected_review_digest:
            raise ApprovalConflict("Review authority became stale before approval reservation")

        reservation = await self.approvals.reserve(
            tenant_id=tenant_id,
            content_id=refreshed.content_id,
            revision_id=revision_id,
            review_digest=refreshed.review_digest,
            approved_by=approved_by,
            approved_at=clock,
        )
        persisted_revision = await self.production.get_revision(tenant_id, revision_id)
        persisted_report = await self.quality.get_report(tenant_id, persisted_revision.qa_report_id)
        if persisted_revision is None or persisted_report is None:
            raise ApprovalAuthorityError("Approval authority disappeared before bundle construction")
        bundle_payload = {
            "schema_version": 2,
            "approval_id": reservation.approval_id,
            "tenant_id": tenant_id,
            "content_id": refreshed.content_id,
            "revision_id": revision_id,
            "profile_snapshot_digest": refreshed.profile_snapshot_digest,
            "plan_digest": refreshed.plan_digest,
            "research_digest": refreshed.research_digest,
            "content_digest": refreshed.content_digest,
            "visual_spec_digest": refreshed.visual_spec_digest,
            "assets": [
                ApprovalAssetV2(asset_id=asset_id, sha256=digest)
                for asset_id, digest in zip(
                    persisted_revision.asset_refs,
                    refreshed.asset_digests,
                    strict=True,
                )
            ],
            "qa_digest": refreshed.qa_digest,
            "policy_version": persisted_report.policy_version,
            "approved_by": reservation.approved_by,
            "approved_at": reservation.approved_at,
        }
        bundle_hash = canonical_approval_sha256(bundle_payload)
        bundle = ApprovalBundleV2(**bundle_payload, bundle_sha256=bundle_hash)
        await self.approvals.save_bundle(bundle)

        bound = await self.approvals.bind_approval(
            content_id=bundle.content_id,
            revision_id=bundle.revision_id,
            approval_id=bundle.approval_id,
            now=clock,
        )
        if not bound:
            raise ApprovalConflict("ContentItem changed before immutable Approval could be bound")
        return bundle

    async def fork_human_edit(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        expected_review_digest: str,
        edited_content: ContentSpecV1,
        now: datetime | None = None,
    ) -> HumanEditResult:
        snapshot = await self.review_snapshot(tenant_id=tenant_id, revision_id=revision_id)
        if snapshot.review_digest != expected_review_digest:
            raise ApprovalConflict("Review authority changed; refresh before editing")

        source_revision = await self.production.get_revision(tenant_id, revision_id)
        source_run = await self.production.get_run(tenant_id, source_revision.run_id)
        source_content = ContentSpecV1.model_validate(snapshot.content)
        if edited_content.content_spec_id == source_content.content_spec_id:
            raise ApprovalAuthorityError("Human edit must create a new ContentSpec identity")
        if edited_content.plan_id != source_content.plan_id:
            raise ApprovalAuthorityError("Human edit cannot change ContentPlan authority")
        if edited_content.format != source_content.format:
            raise ApprovalAuthorityError("Format changes require replanning, not an S7 text edit")
        if edited_content.language != source_content.language:
            raise ApprovalAuthorityError("Language changes require replanning")

        research_record = await self.production.get_artifact(tenant_id, source_run.research_pack_ref)
        claims = {
            claim["claim_id"]: claim
            for claim in (research_record.get("payload", {}).get("claims", []) if research_record else [])
        }
        unknown = set(edited_content.claims_used) - set(claims)
        forbidden = {
            claim_id
            for claim_id in edited_content.claims_used
            if claim_id in claims and claims[claim_id].get("publishability") == ClaimPublishability.FORBIDDEN.value
        }
        if unknown or forbidden:
            raise ApprovalAuthorityError("Human edit cannot introduce unsupported or forbidden claim authority")

        clock = now or utc_now()
        new_revision_id = str(uuid4())
        new_run_id = str(uuid4())
        source_payload = source_content.model_dump(mode="json")
        edited_payload = edited_content.model_dump(mode="json")
        changed_roots = {
            key
            for key in type(source_content).model_fields
            if source_payload.get(key) != edited_payload.get(key)
        }
        changed_roots.discard("content_spec_id")

        cloned_visual: VisualSpecV1 | None = None
        invalidated = ["QAReport", "Approval"]
        if source_revision.visual_spec_ref:
            source_visual = await self.visual.get_visual_spec(source_revision.visual_spec_ref)
            if source_visual is None:
                raise ApprovalAuthorityError("Source VisualSpec is unavailable")
            referenced_roots = {
                block.copy_ref.split(".", 1)[0]
                for page in source_visual.pages
                for block in page.blocks
                if isinstance(block, TextBlockV1) and block.editorial_critical and block.copy_ref
            }
            visual_invalidated = bool(changed_roots & referenced_roots) or "format_spec" in changed_roots
            if visual_invalidated:
                invalidated.extend(["VisualSpec", "Assets", "VisualQA"])
            else:
                cloned_visual = source_visual.model_copy(
                    update={
                        "visual_spec_id": str(uuid4()),
                        "content_spec_id": edited_content.content_spec_id,
                        "revision_id": new_revision_id,
                        "supersedes_visual_spec_id": source_visual.visual_spec_id,
                    }
                )
                invalidated.append("Assets")

        visual_digest = canonical_visual_sha256(cloned_visual) if cloned_visual else None
        run = GenerationRunV1(
            run_id=new_run_id,
            tenant_id=tenant_id,
            content_id=source_run.content_id,
            profile_id=source_run.profile_id,
            profile_version=source_run.profile_version,
            profile_snapshot_digest=source_run.profile_snapshot_digest,
            plan_id=source_run.plan_id,
            plan_digest=source_run.plan_digest,
            state=GenerationRunState.VISUAL_PLANNING,
            contract_versions=tuple(dict.fromkeys((*source_run.contract_versions, "HumanEditV1@1"))),
            research_pack_ref=source_run.research_pack_ref,
            content_spec_ref=edited_content.content_spec_id,
            visual_spec_ref=cloned_visual.visual_spec_id if cloned_visual else None,
            started_at=clock,
        )
        revision = ContentRevisionV1(
            revision_id=new_revision_id,
            tenant_id=tenant_id,
            content_id=source_revision.content_id,
            run_id=new_run_id,
            parent_revision_id=source_revision.revision_id,
            source=RevisionSource.HUMAN_EDIT,
            content_spec_ref=edited_content.content_spec_id,
            content_spec_digest=production_sha256(edited_content),
            visual_spec_ref=cloned_visual.visual_spec_id if cloned_visual else None,
            visual_spec_digest=visual_digest,
            asset_refs=(),
            qa_report_id=None,
            status=RevisionStatus.DRAFT,
            created_at=clock,
        )

        await self.production.create_run(run)
        await self.production.save_artifact(
            tenant_id=tenant_id,
            run_id=new_run_id,
            artifact_type="ContentSpecV1",
            artifact_id=edited_content.content_spec_id,
            digest=revision.content_spec_digest,
            payload=edited_content.model_dump(mode="json"),
        )
        invalidation_payload = {
            "source_revision_id": revision_id,
            "new_revision_id": new_revision_id,
            "changed_roots": sorted(changed_roots),
            "invalidated": list(dict.fromkeys(invalidated)),
            "visual_reused": cloned_visual is not None,
        }
        await self.production.save_artifact(
            tenant_id=tenant_id,
            run_id=new_run_id,
            artifact_type="HumanEditInvalidationV1",
            artifact_id=f"edit-invalidation-{new_revision_id}",
            digest=canonical_approval_sha256(invalidation_payload),
            payload=invalidation_payload,
        )
        await self.production.save_revision(revision)
        if cloned_visual is not None:
            await self.visual.save_visual_spec(cloned_visual)

        item = await self.planning.get_content_item(source_revision.content_id)
        if item is None or item.current_revision_id != revision_id:
            raise ApprovalConflict("ContentItem changed before human edit could be bound")
        changed = await self.planning.transition_content_item(
            item.content_id,
            expected_state=item.editorial_state,
            new_state=ContentEditorialState.REVISION_REQUIRED,
            current_revision_id=new_revision_id,
            now=clock,
        )
        if not changed:
            raise ApprovalConflict("ContentItem changed before human edit could be bound")
        return HumanEditResult(
            revision=revision,
            run=run,
            visual_reused=cloned_visual is not None,
            invalidated=tuple(dict.fromkeys(invalidated)),
        )
