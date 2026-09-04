from typing import Any

from pymongo.errors import DuplicateKeyError

from domain.profiles.models import Profile, ProfileVersion
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return value


class MongoProfileRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.profiles = TenantScopedMongoRepository(db, "profiles", context)
        self.versions = TenantScopedMongoRepository(db, "profile_versions", context)

    async def list_profiles(self) -> list[Profile]:
        documents = await self.profiles.find_many(
            {"status": {"$ne": "ARCHIVED"}}, sort=[("updated_at", -1)]
        )
        return [Profile.model_validate(_clean(document)) for document in documents]

    async def get_profile(self, profile_id: str) -> Profile | None:
        return self._profile(await self.profiles.find_one({"profile_id": profile_id}))

    async def get_version(self, profile_id: str, version: int) -> ProfileVersion | None:
        document = _clean(await self.versions.find_one({"profile_id": profile_id, "version": version}))
        return ProfileVersion.model_validate(document) if document else None

    async def create(self, profile: Profile, version: ProfileVersion) -> None:
        await self.versions.insert_one(version.model_dump())
        try:
            await self.profiles.insert_one(profile.model_dump())
        except Exception:
            await self.versions.delete_one({"profile_id": profile.profile_id, "version": version.version})
            raise

    async def append_version(self, profile: Profile, version: ProfileVersion, expected_version: int) -> bool:
        try:
            await self.versions.insert_one(version.model_dump())
        except DuplicateKeyError:
            return False
        result = await self.profiles.update_one(
            {"profile_id": profile.profile_id, "current_version": expected_version},
            {"$set": {
                "current_version": profile.current_version,
                "name": profile.name,
                "updated_at": profile.updated_at,
            }},
        )
        if result.matched_count == 1:
            return True
        await self.versions.delete_one({"profile_id": profile.profile_id, "version": version.version})
        return False

    @staticmethod
    def _profile(document: dict | None) -> Profile | None:
        value = _clean(document)
        return Profile.model_validate(value) if value else None
