from __future__ import annotations

from typing import Any

from domain.rendering.models import GeneratedSourceAssetV1, canonical_render_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.rendering import MongoRenderingRepository, _clean
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


class MongoR4RenderingRepository(MongoRenderingRepository):
    """R4 extension for immutable provider-generated source image metadata.

    There is at most one generated source identity for one frozen
    (revision, VisualSpec, requirement). This prevents prompt/provider drift from
    creating ambiguous QA/restart authority under an unchanged VisualSpec.
    """

    def __init__(self, db: Any, context: TenantContext):
        super().__init__(db, context)
        self.source_assets = TenantScopedMongoRepository(db, "generated_source_assets", context)

    @staticmethod
    def _rehydrate(document) -> GeneratedSourceAssetV1:
        stored_digest = document.get("metadata_digest")
        asset = GeneratedSourceAssetV1.model_validate(_clean(document, digest_field="metadata_digest"))
        if stored_digest != canonical_render_sha256(asset):
            raise ValueError("persisted GeneratedSourceAssetV1 metadata digest mismatch")
        return asset

    async def get_source_asset(self, source_asset_id: str) -> GeneratedSourceAssetV1 | None:
        document = await self.source_assets.find_one({"source_asset_id": source_asset_id})
        return self._rehydrate(document) if document is not None else None

    async def find_source_asset(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        visual_spec_id: str,
        requirement_id: str,
    ) -> GeneratedSourceAssetV1 | None:
        if tenant_id != self.context.tenant_id:
            raise ValueError("GeneratedSourceAssetV1 tenant authority mismatch")
        document = await self.source_assets.find_one(
            {
                "revision_id": revision_id,
                "visual_spec_id": visual_spec_id,
                "requirement_id": requirement_id,
            }
        )
        return self._rehydrate(document) if document is not None else None

    async def save_source_asset(self, asset: GeneratedSourceAssetV1) -> None:
        if asset.tenant_id != self.context.tenant_id:
            raise ValueError("GeneratedSourceAssetV1 tenant authority mismatch")
        existing_identity = await self.find_source_asset(
            tenant_id=asset.tenant_id,
            revision_id=asset.revision_id,
            visual_spec_id=asset.visual_spec_id,
            requirement_id=asset.requirement_id,
        )
        if existing_identity is not None:
            if existing_identity != asset:
                raise ValueError("GeneratedSourceAssetV1 requirement lineage collision")
            return
        digest = canonical_render_sha256(asset)
        payload = asset.model_dump(mode="json")
        payload["metadata_digest"] = digest
        await self.source_assets.insert_one(payload)
