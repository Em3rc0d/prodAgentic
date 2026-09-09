from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

import pytest

from application.exporting.service import ManualExportAuthorityError, ManualExportService
from domain.approval.models import ApprovalAssetV2, ApprovalBundleV2, canonical_approval_sha256
from domain.exporting.models import ManualExportManifestV1
from domain.production.models import (
    ContentRevisionV1,
    ContentSpecV1,
    RevisionSource,
    RevisionStatus,
    SingleImageSpecV1,
    canonical_sha256 as production_sha256,
)
from domain.rendering.models import AssetV1


NOW = datetime(2026, 9, 9, 16, 30, tzinfo=timezone.utc)
DATA = b"s8-exact-approved-png-bytes"
ACTOR_MARKER = "operator-secret-marker-must-not-export"


def make_content() -> ContentSpecV1:
    return ContentSpecV1(
        content_spec_id="content-spec-s8",
        plan_id="plan-s8",
        language="en",
        title="Internal working title",
        hook="Ship the exact approved content.",
        body="Manual export is a first-class completion path.",
        cta="Publish it through the channel you control.",
        hashtags=("#s8", "#fallback"),
        format="single_image",
        format_spec=SingleImageSpecV1(
            headline="Ship the exact approved content.",
            supporting_copy=("Exact bytes", "Verified hashes"),
        ),
        claims_used=(),
    )


def make_fixture():
    content = make_content()
    content_digest = production_sha256(content)
    asset_sha = hashlib.sha256(DATA).hexdigest()
    revision = ContentRevisionV1(
        revision_id="revision-s8",
        tenant_id="tenant-s8",
        content_id="content-s8",
        run_id="run-s8",
        source=RevisionSource.GENERATION,
        content_spec_ref=content.content_spec_id,
        content_spec_digest=content_digest,
        asset_refs=("asset-s8",),
        qa_report_id="qa-s8",
        status=RevisionStatus.REVIEWABLE,
        created_at=NOW,
    )
    asset = AssetV1(
        asset_id="asset-s8",
        tenant_id="tenant-s8",
        revision_id=revision.revision_id,
        render_id="render-s8",
        visual_spec_id="visual-s8",
        page_id="page-0",
        page_index=0,
        content_type="image/png",
        width=1080,
        height=1350,
        byte_size=len(DATA),
        storage_key="renders/t-s8/r-s8/render-s8/page-00.png",
        sha256=asset_sha,
        render_input_digest="e" * 64,
        created_at=NOW,
    )
    payload = {
        "schema_version": 2,
        "approval_id": "approval-s8",
        "tenant_id": "tenant-s8",
        "content_id": revision.content_id,
        "revision_id": revision.revision_id,
        "profile_snapshot_digest": "1" * 64,
        "plan_digest": "2" * 64,
        "research_digest": "3" * 64,
        "content_digest": content_digest,
        "visual_spec_digest": None,
        "assets": [ApprovalAssetV2(asset_id=asset.asset_id, sha256=asset_sha)],
        "qa_digest": "6" * 64,
        "policy_version": "qa-policy-s8",
        "approved_by": ACTOR_MARKER,
        "approved_at": NOW,
    }
    bundle = ApprovalBundleV2(
        **payload,
        bundle_sha256=canonical_approval_sha256(payload),
    )
    return content, revision, asset, bundle


class ApprovalFake:
    def __init__(self, bundle, *, ignore_tenant=False):
        self.bundle = bundle
        self.ignore_tenant = ignore_tenant

    async def get_bundle(self, tenant_id, approval_id):
        if approval_id != self.bundle.approval_id:
            return None
        if self.ignore_tenant or tenant_id == self.bundle.tenant_id:
            return self.bundle
        return None


class ProductionFake:
    def __init__(self, content, revision, *, ignore_tenant=False):
        self.content = content
        self.revision = revision
        self.ignore_tenant = ignore_tenant

    async def get_revision(self, tenant_id, revision_id):
        if revision_id != self.revision.revision_id:
            return None
        if self.ignore_tenant or tenant_id == self.revision.tenant_id:
            return self.revision
        return None

    async def get_artifact(self, tenant_id, artifact_id):
        if artifact_id != self.content.content_spec_id:
            return None
        if not self.ignore_tenant and tenant_id != self.revision.tenant_id:
            return None
        return {
            "digest": production_sha256(self.content),
            "payload": self.content.model_dump(mode="json"),
        }


class RenderingFake:
    def __init__(self, asset):
        self.asset = asset

    async def get_asset(self, asset_id):
        return self.asset if asset_id == self.asset.asset_id else None


class AssetStoreFake:
    def __init__(self, reads):
        self.reads = list(reads)
        self.index = 0

    async def get(self, storage_key):
        if not self.reads:
            raise FileNotFoundError(storage_key)
        value = self.reads[min(self.index, len(self.reads) - 1)]
        self.index += 1
        if isinstance(value, Exception):
            raise value
        return value


def make_service(*, reads=(DATA, DATA), ignore_tenant=False):
    content, revision, asset, bundle = make_fixture()
    return (
        ManualExportService(
            approval_repository=ApprovalFake(bundle, ignore_tenant=ignore_tenant),
            production_repository=ProductionFake(content, revision, ignore_tenant=ignore_tenant),
            rendering_repository=RenderingFake(asset),
            asset_store=AssetStoreFake(reads),
        ),
        bundle,
    )


async def package_bytes(service):
    package = await service.build(tenant_id="tenant-s8", approval_id="approval-s8")
    try:
        return package, package.stream.read()
    finally:
        package.stream.close()


@pytest.mark.asyncio
async def test_s8_manual_export_is_deterministic_exact_and_secret_free():
    service_a, bundle = make_service()
    package_a, bytes_a = await package_bytes(service_a)

    service_b, _ = make_service()
    package_b, bytes_b = await package_bytes(service_b)

    assert bytes_a == bytes_b
    assert package_a.sha256 == package_b.sha256 == hashlib.sha256(bytes_a).hexdigest()
    assert package_a.manifest.approval_bundle_sha256 == bundle.bundle_sha256
    assert ACTOR_MARKER.encode("utf-8") not in bytes_a

    with zipfile.ZipFile(io.BytesIO(bytes_a), "r") as archive:
        assert archive.namelist() == ["manifest.json", "caption.txt", "assets/page-01.png"]
        manifest = ManualExportManifestV1.model_validate(
            json.loads(archive.read("manifest.json").decode("utf-8"))
        )
        caption = archive.read("caption.txt")
        assert caption == (
            b"Ship the exact approved content.\n\n"
            b"Manual export is a first-class completion path.\n\n"
            b"Publish it through the channel you control.\n\n"
            b"#s8 #fallback\n"
        )
        assert manifest.caption_sha256 == hashlib.sha256(caption).hexdigest()
        assert manifest.content_digest == bundle.content_digest
        assert manifest.qa_digest == bundle.qa_digest
        assert manifest.assets[0].asset_id == "asset-s8"
        assert manifest.assets[0].sha256 == hashlib.sha256(DATA).hexdigest()
        assert archive.read("assets/page-01.png") == DATA


@pytest.mark.asyncio
async def test_s8_rejects_asset_bytes_tampered_after_approval():
    service, _ = make_service(reads=(DATA + b"-tampered",))
    with pytest.raises(ManualExportAuthorityError, match="bytes/hash changed"):
        await service.build(tenant_id="tenant-s8", approval_id="approval-s8")


@pytest.mark.asyncio
async def test_s8_revalidates_assets_again_during_zip_emission():
    service, _ = make_service(reads=(DATA, DATA + b"-changed-between-passes"))
    with pytest.raises(ManualExportAuthorityError, match="bytes/hash changed"):
        await service.build(tenant_id="tenant-s8", approval_id="approval-s8")


@pytest.mark.asyncio
async def test_s8_fails_closed_even_if_repository_accidentally_returns_other_tenant_bundle():
    service, _ = make_service(ignore_tenant=True)
    with pytest.raises(ManualExportAuthorityError, match="not found"):
        await service.build(tenant_id="tenant-other", approval_id="approval-s8")
