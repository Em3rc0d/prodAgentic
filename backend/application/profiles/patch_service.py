from __future__ import annotations

from datetime import datetime

from domain.profiles.models import (
    CopyPolicy,
    EditorialStrategy,
    Profile,
    ProfileVersion,
    canonical_digest,
)
from domain.profiles.patches import ProfileVersionPatch
from domain.profiles.ports import ProfileRepositoryPort

from .service import AcceptedProfile, ProfileConflict


class ProfilePatchNoop(ValueError):
    pass


def _append_unique(existing: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *additions)))


class ProfilePatchService:
    """Create a new immutable ProfileVersion from an allowlisted patch.

    The caller supplies a stable `accepted_at` (for example a persisted human
    decision timestamp), which makes crash retries recreate the same version
    digest instead of inventing a new semantic acceptance event.
    """

    def __init__(self, repository: ProfileRepositoryPort):
        self.repository = repository

    @staticmethod
    def build_version(
        current: ProfileVersion,
        patch: ProfileVersionPatch,
        *,
        accepted_at: datetime,
    ) -> ProfileVersion:
        if patch.replace_topic_families is not None:
            topic_families = patch.replace_topic_families
        else:
            topic_families = _append_unique(
                current.editorial_strategy.topic_families,
                patch.add_topic_families,
            )
        hook_tendencies = _append_unique(
            current.copy_policy.hook_tendencies,
            patch.add_hook_tendencies,
        )
        if (
            topic_families == current.editorial_strategy.topic_families
            and hook_tendencies == current.copy_policy.hook_tendencies
        ):
            raise ProfilePatchNoop("Profile patch does not change current authority")

        editorial_strategy = EditorialStrategy(
            topic_families=topic_families,
            excluded_topics=current.editorial_strategy.excluded_topics,
        )
        copy_policy = CopyPolicy(
            **current.copy_policy.model_dump(
                mode="python",
                exclude={"hook_tendencies"},
            ),
            hook_tendencies=hook_tendencies,
        )
        payload = current.model_dump(
            mode="python",
            exclude={
                "version",
                "editorial_strategy",
                "copy_policy",
                "accepted_at",
                "created_at",
                "digest",
            },
        )
        provisional = ProfileVersion(
            **payload,
            version=current.version + 1,
            editorial_strategy=editorial_strategy,
            copy_policy=copy_policy,
            accepted_at=accepted_at,
            created_at=accepted_at,
            digest="0" * 64,
        )
        return provisional.model_copy(update={"digest": canonical_digest(provisional)})

    async def apply(
        self,
        *,
        tenant_id: str,
        profile_id: str,
        expected_current_version: int,
        patch: ProfileVersionPatch,
        accepted_at: datetime,
    ) -> AcceptedProfile:
        profile = await self.repository.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        if profile.tenant_id != tenant_id or profile.current_version != expected_current_version:
            raise ProfileConflict("Profile version changed; reload before applying this decision")

        current = await self.repository.get_version(profile_id, expected_current_version)
        if current is None:
            raise RuntimeError("Current ProfileVersion is unavailable")

        version = self.build_version(current, patch, accepted_at=accepted_at)
        next_version_number = version.version
        updated = Profile(
            **profile.model_dump(exclude={"current_version", "name", "updated_at"}),
            current_version=next_version_number,
            name=version.identity.name,
            updated_at=version.accepted_at,
        )
        if not await self.repository.append_version(updated, version, expected_current_version):
            raise ProfileConflict("Profile version changed; reload before applying this decision")

        committed = await self.repository.get_version(profile_id, next_version_number)
        if committed is None or committed.digest != version.digest:
            raise RuntimeError("Profile patch committed without matching immutable evidence")
        committed_profile = updated.model_copy(
            update={"name": committed.identity.name, "updated_at": committed.accepted_at}
        )
        return AcceptedProfile(committed_profile, committed)
