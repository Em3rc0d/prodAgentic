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

    async def _advance_pointer_from_version(
        self,
        version: ProfileVersion,
        expected_version: int,
    ) -> bool:
        """Finish an interrupted version->pointer commit using immutable evidence.

        ProfileVersion is inserted before the mutable Profile pointer advances. If
        the process dies in between, the immutable version is durable intent. A
        later retry must finish that intent instead of deleting or overwriting it.
        """
        result = await self.profiles.update_one(
            {"profile_id": version.profile_id, "current_version": expected_version},
            {"$set": {
                "current_version": version.version,
                "name": version.identity.name,
                "updated_at": version.accepted_at,
            }},
        )
        if result.matched_count == 1:
            return True
        current = await self.get_profile(version.profile_id)
        return current is not None and current.current_version >= version.version

    async def append_version(self, profile: Profile, version: ProfileVersion, expected_version: int) -> bool:
        try:
            await self.versions.insert_one(version.model_dump())
        except DuplicateKeyError:
            persisted = await self.get_version(profile.profile_id, version.version)
            if persisted is None:
                return False

            # A duplicate next-version can be the durable half of a request that
            # crashed after inserting ProfileVersion and before advancing Profile.
            # Recover that already accepted version first. Never replace it with a
            # competing retry and never delete immutable history during recovery.
            current = await self.get_profile(profile.profile_id)
            if current is not None and current.current_version == expected_version:
                await self._advance_pointer_from_version(persisted, expected_version)

            if persisted.digest != version.digest:
                return False
            current = await self.get_profile(profile.profile_id)
            return current is not None and current.current_version >= version.version

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

        # Do not compensate by deleting the immutable version. Another process may
        # already be recovering this exact durable intent. Re-read authority and
        # accept success only when the persisted next-version is exactly ours.
        persisted = await self.get_version(profile.profile_id, version.version)
        current = await self.get_profile(profile.profile_id)
        return (
            persisted is not None
            and persisted.digest == version.digest
            and current is not None
            and current.current_version >= version.version
        )

    @staticmethod
    def _profile(document: dict | None) -> Profile | None:
        value = _clean(document)
        return Profile.model_validate(value) if value else None
