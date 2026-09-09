from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from application.approval.service import ApprovalAuthorityError, ApprovalConflict, ApprovalService
from application.quality.policy import build_qa_report
from domain.approval.models import ApprovalReservationV1
from domain.planning.models import ContentEditorialState, ContentItem
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
    ContentRevisionV1,
    ContentSpecV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
    SingleImageSpecV1,
    canonical_sha256 as production_sha256,
)
from domain.rendering.models import AssetV1


NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
DATA = b"s7-owned-approved-bytes"


def make_profile():
    provisional = ProfileVersion(
        profile_id="profile-s7", tenant_id="tenant-s7", version=1,
        identity=ProfileIdentity(name="S7", account_type=AccountType.NICHE, summary="S7 fixture"),
        goals=(Goal.EDUCATE,), audience=("readers",), editorial_strategy=EditorialStrategy(),
        novelty_policy=NoveltyPolicy(), copy_policy=CopyPolicy(voice_traits=("clear",), target_language="en"),
        claim_policy=ClaimPolicy(), visual_system=VisualSystem(),
        publishing_preferences=PublishingPreferences(channels=(Channel.LINKEDIN,), default_batch_size=4),
        agent_policy=AgentPolicy(), provenance=MigrationProvenance(source="USER_ACCEPTED"),
        accepted_at=NOW, created_at=NOW, digest="0" * 64,
    )
    return provisional.model_copy(update={"digest": profile_digest(provisional)})


def make_content(content_spec_id="content-spec-s7", body="Exact approval body"):
    return ContentSpecV1(
        content_spec_id=content_spec_id, plan_id="plan-s7", language="en", title="S7",
        hook="Approve exact authority", body=body, cta="Inspect the receipt", hashtags=("#s7",),
        format="single_image",
        format_spec=SingleImageSpecV1(headline="Approve exact authority", supporting_copy=("Immutable",)),
        claims_used=(),
    )


def fixtures():
    profile = make_profile()
    content = make_content()
    content_digest = production_sha256(content)
    sha = hashlib.sha256(DATA).hexdigest()
    run = GenerationRunV1(
        run_id="run-s7", tenant_id="tenant-s7", content_id="content-s7",
        profile_id=profile.profile_id, profile_version=profile.version, profile_snapshot_digest=profile.digest,
        plan_id="plan-s7", plan_digest="b" * 64, state=GenerationRunState.COMPLETED,
        contract_versions=("ContentSpecV1@1",), research_pack_ref="research-s7",
        content_spec_ref=content.content_spec_id, qa_report_refs=("qa-s7",),
        started_at=NOW, completed_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s7", tenant_id=run.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=content.content_spec_id,
        content_spec_digest=content_digest, asset_refs=("asset-s7",), qa_report_id="qa-s7",
        status=RevisionStatus.REVIEWABLE, created_at=NOW,
    )
    asset = AssetV1(
        asset_id="asset-s7", tenant_id=run.tenant_id, revision_id=revision.revision_id,
        render_id="render-s7", visual_spec_id="visual-s7", page_id="page-0", page_index=0,
        content_type="image/png", width=1080, height=1350, byte_size=len(DATA),
        storage_key="renders/t-aaaa/r-bbbb/x-cccc/page-00.png", sha256=sha,
        render_input_digest="e" * 64, created_at=NOW,
    )
    report = build_qa_report(
        qa_report_id="qa-s7", tenant_id=run.tenant_id, revision_id=revision.revision_id,
        content_spec_digest=content_digest, render_input_digest=asset.render_input_digest,
        asset_digests=(sha,), deterministic_checks=(), semantic_checks=(), visual_checks=(), created_at=NOW,
    )
    item = ContentItem(
        content_id=run.content_id, tenant_id=run.tenant_id, batch_id="batch-s7",
        profile_id=profile.profile_id, profile_version=1, canonical_topic="s7", angle="authority",
        role="educate", target_effect="trust", format="single_image", hook_pattern="question",
        editorial_state=ContentEditorialState.PRODUCING, current_revision_id=revision.revision_id,
        created_at=NOW, updated_at=NOW,
    )
    return profile, content, run, revision, asset, report, item


class PlanningFake:
    def __init__(self, item): self.item = item
    async def get_content_item(self, content_id): return self.item if content_id == self.item.content_id else None
    async def transition_content_item(self, content_id, *, expected_state, new_state, current_revision_id=None, now):
        if content_id != self.item.content_id or self.item.editorial_state != expected_state: return False
        self.item = self.item.model_copy(update={
            "editorial_state": new_state,
            "current_revision_id": current_revision_id or self.item.current_revision_id,
            "updated_at": now,
        })
        return True


class ProfilesFake:
    def __init__(self, profile): self.profile = profile
    async def get_version(self, profile_id, version):
        return self.profile if profile_id == self.profile.profile_id and version == self.profile.version else None


class ProductionFake:
    def __init__(self, run, revision, content):
        self.run, self.revision, self.content = run, revision, content
        self.saved_runs, self.saved_revisions, self.saved_artifacts = [], [], []
    async def get_revision(self, tenant_id, revision_id):
        return self.revision if tenant_id == self.revision.tenant_id and revision_id == self.revision.revision_id else None
    async def get_run(self, tenant_id, run_id): return self.run if tenant_id == self.run.tenant_id and run_id == self.run.run_id else None
    async def get_artifact(self, tenant_id, artifact_id):
        if artifact_id == "research-s7": return {"digest": "c" * 64, "payload": {"claims": []}}
        if artifact_id == self.content.content_spec_id:
            return {"digest": production_sha256(self.content), "payload": self.content.model_dump(mode="json")}
        return None
    async def create_run(self, run): self.saved_runs.append(run)
    async def save_revision(self, revision): self.saved_revisions.append(revision)
    async def save_artifact(self, **kwargs): self.saved_artifacts.append(kwargs)


class VisualFake:
    async def get_visual_spec(self, visual_spec_id): return None
    async def save_visual_spec(self, spec): raise AssertionError("visual should not be cloned in this fixture")


class RenderingFake:
    def __init__(self, asset): self.asset = asset
    async def get_asset(self, asset_id): return self.asset if asset_id == self.asset.asset_id else None


class QualityFake:
    def __init__(self, report): self.report = report
    async def get_report(self, tenant_id, qa_report_id):
        return self.report if tenant_id == self.report.tenant_id and qa_report_id == self.report.qa_report_id else None


class AssetStoreFake:
    def __init__(self, data): self.data = data
    async def get(self, storage_key): return self.data


class ApprovalFake:
    def __init__(self): self.bundle = None; self.ready = False; self.bound = False; self.reservation = None
    async def get_by_revision(self, tenant_id, revision_id): return self.bundle
    async def get_bundle(self, tenant_id, approval_id): return self.bundle if self.bundle and self.bundle.approval_id == approval_id else None
    async def ensure_ready_for_review(self, *, content_id, revision_id, now): self.ready = True; return True
    async def reserve(self, *, tenant_id, content_id, revision_id, review_digest, approved_by, approved_at):
        if self.reservation is None:
            self.reservation = ApprovalReservationV1(
                approval_id="approval-s7", tenant_id=tenant_id, content_id=content_id,
                revision_id=revision_id, review_digest=review_digest, approved_by=approved_by, approved_at=approved_at,
            )
        return self.reservation
    async def save_bundle(self, bundle): self.bundle = bundle
    async def bind_approval(self, *, content_id, revision_id, approval_id, now): self.bound = True; return True


def make_service(*, tampered=False):
    profile, content, run, revision, asset, report, item = fixtures()
    approvals = ApprovalFake()
    production = ProductionFake(run, revision, content)
    planning = PlanningFake(item)
    service = ApprovalService(
        planning_repository=planning, profile_repository=ProfilesFake(profile), production_repository=production,
        visual_repository=VisualFake(), rendering_repository=RenderingFake(asset), quality_repository=QualityFake(report),
        approval_repository=approvals, asset_store=AssetStoreFake(DATA + (b"tamper" if tampered else b"")),
    )
    return service, approvals, production, planning, content


@pytest.mark.asyncio
async def test_s7_approval_binds_exact_review_digest_and_owned_bytes():
    service, approvals, _, _, _ = make_service()
    snapshot = await service.review_snapshot(tenant_id="tenant-s7", revision_id="revision-s7")
    assert snapshot.approval_available is True
    bundle = await service.approve(
        tenant_id="tenant-s7", revision_id="revision-s7", expected_review_digest=snapshot.review_digest,
        approved_by="operator-s7", now=NOW,
    )
    assert bundle.revision_id == "revision-s7"
    assert bundle.assets[0].sha256 == hashlib.sha256(DATA).hexdigest()
    assert approvals.ready and approvals.bound
    assert approvals.bundle == bundle


@pytest.mark.asyncio
async def test_s7_stale_review_digest_is_blocked_before_reservation():
    service, approvals, _, _, _ = make_service()
    with pytest.raises(ApprovalConflict, match="refresh"):
        await service.approve(
            tenant_id="tenant-s7", revision_id="revision-s7", expected_review_digest="0" * 64,
            approved_by="operator-s7", now=NOW,
        )
    assert approvals.reservation is None and approvals.bundle is None


@pytest.mark.asyncio
async def test_s7_rehashes_owned_bytes_and_rejects_post_qa_tampering():
    service, approvals, _, _, _ = make_service(tampered=True)
    with pytest.raises(ApprovalAuthorityError, match="bytes/hash"):
        await service.review_snapshot(tenant_id="tenant-s7", revision_id="revision-s7")
    assert approvals.bundle is None


@pytest.mark.asyncio
async def test_s7_human_edit_creates_new_revision_without_mutating_source():
    service, _, production, planning, content = make_service()
    snapshot = await service.review_snapshot(tenant_id="tenant-s7", revision_id="revision-s7")
    edited = make_content(content_spec_id="content-spec-s7-edit", body="Human-edited body")
    result = await service.fork_human_edit(
        tenant_id="tenant-s7", revision_id="revision-s7", expected_review_digest=snapshot.review_digest,
        edited_content=edited, now=NOW,
    )
    assert result.revision.revision_id != "revision-s7"
    assert result.revision.parent_revision_id == "revision-s7"
    assert result.revision.source == RevisionSource.HUMAN_EDIT
    assert result.revision.status == RevisionStatus.DRAFT
    assert production.revision.status == RevisionStatus.REVIEWABLE
    assert planning.item.current_revision_id == result.revision.revision_id
    assert planning.item.editorial_state == ContentEditorialState.REVISION_REQUIRED
