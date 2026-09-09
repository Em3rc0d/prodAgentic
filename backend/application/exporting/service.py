from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from domain.exporting.models import (
    ManualExportAssetV1,
    ManualExportManifestV1,
    canonical_export_json,
    sha256_hex,
)
from domain.production.models import ContentSpecV1, canonical_sha256 as production_sha256
from domain.rendering.ports import AssetStorePort, RenderingRepositoryPort


class ManualExportAuthorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualExportArchive:
    filename: str
    manifest: ManualExportManifestV1
    stream: BinaryIO
    byte_size: int
    sha256: str
    manifest_sha256: str


class ManualExportService:
    """S8 authority: immutable ApprovalBundleV2 -> deterministic manual package projection.

    The ZIP is intentionally ephemeral. ApprovalBundleV2 and its upstream immutable
    evidence remain authoritative; this service never persists export bytes or mutates
    scheduling/publication state.
    """

    def __init__(
        self,
        *,
        approval_repository,
        production_repository,
        rendering_repository: RenderingRepositoryPort,
        asset_store: AssetStorePort,
    ):
        self.approvals = approval_repository
        self.production = production_repository
        self.rendering = rendering_repository
        self.asset_store = asset_store

    async def build(self, *, tenant_id: str, approval_id: str) -> ManualExportArchive:
        approval = await self.approvals.get_bundle(tenant_id, approval_id)
        if approval is None or approval.tenant_id != tenant_id:
            raise ManualExportAuthorityError("ApprovalBundleV2 not found")

        revision = await self.production.get_revision(tenant_id, approval.revision_id)
        if (
            revision is None
            or revision.tenant_id != tenant_id
            or revision.content_id != approval.content_id
            or revision.revision_id != approval.revision_id
        ):
            raise ManualExportAuthorityError("Approved ContentRevision authority mismatch")
        if revision.content_spec_digest != approval.content_digest:
            raise ManualExportAuthorityError("Approved ContentSpec digest differs from revision authority")
        if revision.visual_spec_digest != approval.visual_spec_digest:
            raise ManualExportAuthorityError("Approved VisualSpec digest differs from revision authority")

        expected_asset_ids = tuple(asset.asset_id for asset in approval.assets)
        if tuple(revision.asset_refs) != expected_asset_ids:
            raise ManualExportAuthorityError("Approved asset set/order differs from ContentRevision authority")

        content_record = await self.production.get_artifact(tenant_id, revision.content_spec_ref)
        if content_record is None or content_record.get("digest") != approval.content_digest:
            raise ManualExportAuthorityError("Approved ContentSpec persistence digest mismatch")
        try:
            content = ContentSpecV1.model_validate(content_record.get("payload"))
        except Exception as exc:
            raise ManualExportAuthorityError("Approved ContentSpec payload is invalid") from exc
        if production_sha256(content) != approval.content_digest:
            raise ManualExportAuthorityError("Approved ContentSpec canonical digest mismatch")

        caption_bytes = _caption_bytes(content)
        export_assets: list[ManualExportAssetV1] = []
        asset_descriptors = []

        # Pass one proves current AssetStore ownership before the manifest is created.
        # Bytes are deliberately discarded after hashing so a large carousel is never
        # retained fully in memory.
        for index, approved_asset in enumerate(approval.assets):
            asset = await self.rendering.get_asset(approved_asset.asset_id)
            if (
                asset is None
                or asset.tenant_id != tenant_id
                or asset.revision_id != approval.revision_id
                or asset.asset_id != approved_asset.asset_id
            ):
                raise ManualExportAuthorityError("Approved AssetV1 lineage mismatch")
            if asset.page_index != index:
                raise ManualExportAuthorityError("Approved AssetV1 page order is not canonical")
            if asset.sha256 != approved_asset.sha256:
                raise ManualExportAuthorityError("Approved AssetV1 metadata digest changed")
            data = await self._read_verified_asset(asset, approved_asset.sha256)
            filename = f"assets/page-{index + 1:02d}.png"
            export_assets.append(
                ManualExportAssetV1(
                    asset_id=asset.asset_id,
                    filename=filename,
                    content_type=asset.content_type.value,
                    byte_size=len(data),
                    sha256=approved_asset.sha256,
                )
            )
            asset_descriptors.append((asset, approved_asset.sha256, filename))

        manifest = ManualExportManifestV1(
            approval_id=approval.approval_id,
            approval_bundle_sha256=approval.bundle_sha256,
            content_id=approval.content_id,
            revision_id=approval.revision_id,
            content_spec_id=content.content_spec_id,
            content_digest=approval.content_digest,
            visual_spec_digest=approval.visual_spec_digest,
            qa_digest=approval.qa_digest,
            policy_version=approval.policy_version,
            caption_sha256=sha256_hex(caption_bytes),
            assets=tuple(export_assets),
        )
        manifest_bytes = canonical_export_json(manifest)
        manifest_sha = sha256_hex(manifest_bytes)

        stream = SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                _write_zip_entry(archive, "manifest.json", manifest_bytes)
                _write_zip_entry(archive, "caption.txt", caption_bytes)

                # Pass two closes the race between manifest construction and package
                # emission. If bytes changed/disappeared, export fails rather than
                # emitting a package whose manifest no longer describes owned bytes.
                for asset, expected_sha, filename in asset_descriptors:
                    data = await self._read_verified_asset(asset, expected_sha)
                    _write_zip_entry(archive, filename, data)

            stream.seek(0, 2)
            byte_size = stream.tell()
            stream.seek(0)
            archive_hash = hashlib.sha256()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                archive_hash.update(chunk)
            stream.seek(0)
        except Exception:
            stream.close()
            raise

        return ManualExportArchive(
            filename=f"prodagentic-manual-{approval.bundle_sha256[:12]}.zip",
            manifest=manifest,
            stream=stream,
            byte_size=byte_size,
            sha256=archive_hash.hexdigest(),
            manifest_sha256=manifest_sha,
        )

    async def _read_verified_asset(self, asset, expected_sha: str) -> bytes:
        try:
            data = await self.asset_store.get(asset.storage_key)
        except Exception as exc:
            raise ManualExportAuthorityError("Approved asset bytes are unavailable") from exc
        actual_sha = sha256_hex(data)
        if len(data) != asset.byte_size or actual_sha != asset.sha256 or actual_sha != expected_sha:
            raise ManualExportAuthorityError("Approved asset bytes/hash changed after Approval")
        return data


def _caption_bytes(content: ContentSpecV1) -> bytes:
    sections = [content.hook, content.body]
    if content.cta:
        sections.append(content.cta)
    if content.hashtags:
        sections.append(" ".join(content.hashtags))
    return ("\n\n".join(sections) + "\n").encode("utf-8")


def _write_zip_entry(archive: zipfile.ZipFile, filename: str, data: bytes) -> None:
    info = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    archive.writestr(info, data)
