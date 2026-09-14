from __future__ import annotations

from typing import Any

from domain.rendering.models import GeneratedSourceAssetV1, canonical_render_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.rendering import MongoRenderingRepository, _clean
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


class MongoR4RenderingRepository(MongoRenderingRepository):
    """R4 extension for immutable provider-generated source image metadata.

    Final render AssetV1/RenderResultV1 semantics stay owned by the certified S5
    repository. Generated source assets live in a separate collection and cannot
    be mistaken for final approved render bytes.
    """

    def __init__(self, db: Any, context: TenantContext):
        super().__init__(db, context)
        self.source_assets = TenantScopedMongoRepository(db, "generated_source_assets", context)

    async def get_source_asset(self, source_asset_id: str) -> GeneratedSourceAssetV1 | None:
        document = await self.source_assets.find_one({"source_asset_id": source_asset_id})
        if document is None:
            return None
        stored_digest = document.get("metadata_digest")
        asset = GeneratedSourceAssetV1.model_validate(_clean(document, digest_field="metadata_digest"))
        if stored_digest != canonical_render_sha256(asset):
            raise ValueError("persisted GeneratedSourceAssetV1 metadata digest mismatch")
        return asset

    async def save_source_asset(self, asset: GeneratedSourceAssetV1) -> None:
        if asset.tenant_id != self.context.tenant_id:
            raise ValueError("GeneratedSourceAssetV1 tenant authority mismatch")
        digest = canonical_render_sha256(asset)
        existing = await self.get_source_asset(asset.source_asset_id)
        if existing is not None:
            if existing != asset:
                raise ValueError("GeneratedSourceAssetV1 identity collision")
            return
        payload = asset.model_dump(mode="json")
        payload["metadata_digest"] = digest
        await self.source_assets.insert_one(payload)
