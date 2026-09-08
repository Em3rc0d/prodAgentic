from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.production.models import ContentRevisionV1, utc_now
from domain.tenants.models import TenantContext
from domain.visual.models import DesignProfileV1, VisualSpecV1, canonical_visual_sha256
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


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


def _clean(document: dict | None, *, drop_digest: bool = False) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    value.pop("tenant_id", None)
    value.pop("created_at", None)
    if drop_digest:
        value.pop("digest", None)
    return _hydrate_utc(value)


class MongoVisualRepository:
    """Tenant-scoped durable S4 visual intent and derived design policy."""

    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.design_profiles = TenantScopedMongoRepository(db, "design_profiles", context)
        self.visual_specs = TenantScopedMongoRepository(db, "visual_specs", context)
        self.revisions = TenantScopedMongoRepository(db, "content_revisions", context)

    @staticmethod
    def _verify_design_profile(profile: DesignProfileV1) -> None:
        expected = canonical_visual_sha256(profile, exclude={"design_profile_id", "digest"})
        if expected != profile.digest:
            raise ValueError("DesignProfile digest mismatch")

    async def save_design_profile(self, profile: DesignProfileV1) -> None:
        self._verify_design_profile(profile)
        existing = await self.get_design_profile(profile.design_profile_id)
        if existing is not None:
            if existing != profile:
                raise ValueError("DesignProfile identity collision")
            return
        payload = profile.model_dump()
        payload["created_at"] = utc_now()
        await self.design_profiles.insert_one(payload)

    async def get_design_profile(self, design_profile_id: str) -> DesignProfileV1 | None:
        document = _clean(await self.design_profiles.find_one({"design_profile_id": design_profile_id}))
        if document is None:
            return None
        profile = DesignProfileV1.model_validate(document)
        self._verify_design_profile(profile)
        return profile

    async def save_visual_spec(self, spec: VisualSpecV1) -> None:
        digest = canonical_visual_sha256(spec)
        existing = await self.visual_specs.find_one({"visual_spec_id": spec.visual_spec_id})
        if existing is not None:
            existing_digest = existing.get("digest")
            existing_spec = VisualSpecV1.model_validate(_clean(existing, drop_digest=True))
            if existing_digest != digest or existing_spec != spec:
                raise ValueError("VisualSpec identity collision")
            return
        payload = spec.model_dump()
        payload["digest"] = digest
        payload["created_at"] = utc_now()
        await self.visual_specs.insert_one(payload)

    async def get_visual_spec(self, visual_spec_id: str) -> VisualSpecV1 | None:
        document = await self.visual_specs.find_one({"visual_spec_id": visual_spec_id})
        if document is None:
            return None
        stored_digest = document.get("digest")
        spec = VisualSpecV1.model_validate(_clean(document, drop_digest=True))
        if stored_digest != canonical_visual_sha256(spec):
            raise ValueError("persisted VisualSpec digest mismatch")
        return spec

    async def bind_revision_visual(
        self,
        *,
        revision_id: str,
        expected_visual_spec_ref: str | None,
        visual_spec_ref: str,
        visual_spec_digest: str,
    ) -> ContentRevisionV1 | None:
        result = await self.revisions.update_one(
            {
                "revision_id": revision_id,
                "status": "DRAFT",
                "visual_spec_ref": expected_visual_spec_ref,
                "asset_refs": {"$size": 0},
                "qa_report_id": None,
            },
            {"$set": {"visual_spec_ref": visual_spec_ref, "visual_spec_digest": visual_spec_digest}},
        )
        if result.matched_count != 1:
            return None
        document = await self.revisions.find_one({"revision_id": revision_id})
        if document is None:
            return None
        cleaned = dict(document)
        cleaned.pop("_id", None)
        cleaned = _hydrate_utc(cleaned)
        return ContentRevisionV1.model_validate(cleaned)
