from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.production.models import (
    ContentRevisionV1,
    GenerationFailureV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionStatus,
    utc_now,
)
from domain.rendering.models import AssetV1, RenderResultV1, canonical_render_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


_S5_CONTRACTS = ("RendererRequestV1@1", "AssetV1@1", "RenderResultV1@1")


def _hydrate_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return {key: _hydrate_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_hydrate_utc(item) for item in value]
    return value


def _clean(document: dict | None, *, digest_field: str | None = None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    if digest_field:
        value.pop(digest_field, None)
    return _hydrate_utc(value)


class MongoRenderingRepository:
    """Tenant-scoped S5 render lineage, immutable asset metadata and CAS transitions."""

    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.assets = TenantScopedMongoRepository(db, "assets", context)
        self.render_results = TenantScopedMongoRepository(db, "render_results", context)
        self.revisions = TenantScopedMongoRepository(db, "content_revisions", context)
        self.runs = TenantScopedMongoRepository(db, "generation_runs", context)

    async def get_asset(self, asset_id: str) -> AssetV1 | None:
        document = await self.assets.find_one({"asset_id": asset_id})
        if document is None:
            return None
        stored_digest = document.get("metadata_digest")
        asset = AssetV1.model_validate(_clean(document, digest_field="metadata_digest"))
        if stored_digest != canonical_render_sha256(asset):
            raise ValueError("persisted AssetV1 metadata digest mismatch")
        return asset

    async def save_asset(self, asset: AssetV1) -> None:
        if asset.tenant_id != self.context.tenant_id:
            raise ValueError("AssetV1 tenant authority mismatch")
        digest = canonical_render_sha256(asset)
        existing = await self.get_asset(asset.asset_id)
        if existing is not None:
            if existing != asset:
                raise ValueError("AssetV1 identity collision")
            return
        payload = asset.model_dump()
        payload["metadata_digest"] = digest
        await self.assets.insert_one(payload)

    async def get_render_result(self, render_id: str) -> RenderResultV1 | None:
        document = await self.render_results.find_one({"render_id": render_id})
        if document is None:
            return None
        stored_digest = document.get("result_digest")
        result = RenderResultV1.model_validate(_clean(document, digest_field="result_digest"))
        if stored_digest != canonical_render_sha256(result):
            raise ValueError("persisted RenderResultV1 digest mismatch")
        return result

    async def save_render_result(self, result: RenderResultV1) -> None:
        if result.tenant_id != self.context.tenant_id:
            raise ValueError("RenderResultV1 tenant authority mismatch")
        digest = canonical_render_sha256(result)
        existing = await self.get_render_result(result.render_id)
        if existing is not None:
            if existing != result:
                raise ValueError("RenderResultV1 identity collision")
            return
        payload = result.model_dump()
        payload["result_digest"] = digest
        await self.render_results.insert_one(payload)

    async def _get_run(self, run_id: str) -> GenerationRunV1 | None:
        document = _clean(await self.runs.find_one({"run_id": run_id}))
        return GenerationRunV1.model_validate(document) if document else None

    async def _ensure_contracts(self, run_id: str, visual_spec_ref: str) -> GenerationRunV1 | None:
        await self.runs.update_one(
            {"run_id": run_id, "visual_spec_ref": visual_spec_ref},
            {"$addToSet": {"contract_versions": {"$each": list(_S5_CONTRACTS)}}},
        )
        return await self._get_run(run_id)

    async def claim_run_rendering(self, *, run_id: str, visual_spec_ref: str) -> GenerationRunV1 | None:
        result = await self.runs.update_one(
            {
                "run_id": run_id,
                "state": GenerationRunState.VISUAL_PLANNING.value,
                "visual_spec_ref": visual_spec_ref,
            },
            {
                "$set": {"state": GenerationRunState.RENDERING.value, "failure": None, "completed_at": None},
                "$addToSet": {"contract_versions": {"$each": list(_S5_CONTRACTS)}},
            },
        )
        if result.matched_count == 1:
            return await self._get_run(run_id)
        existing = await self._get_run(run_id)
        if (
            existing is not None
            and existing.visual_spec_ref == visual_spec_ref
            and existing.state in {GenerationRunState.RENDERING, GenerationRunState.QA}
        ):
            return await self._ensure_contracts(run_id, visual_spec_ref)
        return None

    async def finish_run_qa(self, *, run_id: str, visual_spec_ref: str) -> GenerationRunV1 | None:
        result = await self.runs.update_one(
            {
                "run_id": run_id,
                "state": GenerationRunState.RENDERING.value,
                "visual_spec_ref": visual_spec_ref,
            },
            {"$set": {"state": GenerationRunState.QA.value, "failure": None}},
        )
        if result.matched_count == 1:
            return await self._ensure_contracts(run_id, visual_spec_ref)
        existing = await self._get_run(run_id)
        if existing is not None and existing.visual_spec_ref == visual_spec_ref and existing.state == GenerationRunState.QA:
            return await self._ensure_contracts(run_id, visual_spec_ref)
        return None

    async def mark_run_failed(
        self,
        *,
        run_id: str,
        visual_spec_ref: str,
        failure: GenerationFailureV1,
    ) -> GenerationRunV1 | None:
        result = await self.runs.update_one(
            {
                "run_id": run_id,
                "state": GenerationRunState.RENDERING.value,
                "visual_spec_ref": visual_spec_ref,
            },
            {
                "$set": {
                    "state": GenerationRunState.FAILED.value,
                    "failure": failure.model_dump(),
                    "completed_at": utc_now(),
                }
            },
        )
        if result.matched_count == 1:
            return await self._get_run(run_id)
        existing = await self._get_run(run_id)
        if existing is not None and existing.visual_spec_ref == visual_spec_ref and existing.state == GenerationRunState.FAILED:
            return existing
        return None

    async def bind_revision_assets(
        self,
        *,
        revision_id: str,
        visual_spec_ref: str,
        visual_spec_digest: str,
        expected_asset_refs: tuple[str, ...],
        asset_refs: tuple[str, ...],
    ) -> ContentRevisionV1 | None:
        result = await self.revisions.update_one(
            {
                "revision_id": revision_id,
                "status": RevisionStatus.DRAFT.value,
                "visual_spec_ref": visual_spec_ref,
                "visual_spec_digest": visual_spec_digest,
                "asset_refs": list(expected_asset_refs),
                "qa_report_id": None,
            },
            {
                "$set": {
                    "asset_refs": list(asset_refs),
                    "status": RevisionStatus.QA_PENDING.value,
                }
            },
        )
        document = _clean(await self.revisions.find_one({"revision_id": revision_id}))
        if result.matched_count == 1:
            return ContentRevisionV1.model_validate(document) if document else None
        if document is None:
            return None
        existing = ContentRevisionV1.model_validate(document)
        if (
            existing.visual_spec_ref == visual_spec_ref
            and existing.visual_spec_digest == visual_spec_digest
            and existing.asset_refs == asset_refs
            and existing.status == RevisionStatus.QA_PENDING
            and existing.qa_report_id is None
        ):
            return existing
        return None
