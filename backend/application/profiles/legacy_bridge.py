import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from application.profiles.analyzer import DeterministicProfileAnalyzer
from domain.profiles.models import (
    AgentPolicy,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    MigrationProvenance,
    NoveltyPolicy,
    Profile,
    ProfileIdentity,
    ProfileSetup,
    ProfileStatus,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest,
)


MIGRATION_ID = "mk1_s1_profile_bridge_v1"
LEGACY_ALLOWLIST = {
    "profile_id", "version", "name", "display_name", "positioning", "audience", "voice",
    "core_topics", "excluded_topics", "target_language", "min_words", "max_words",
    "forbidden_claims", "banned_phrases", "brand_constraints", "default_visual_style",
    "visual_enabled", "created_at", "updated_at", "archived",
}


@dataclass(frozen=True)
class ProfileBridgeReport:
    migration: str
    tenant_id: str
    scanned: int
    migrated: int
    existing: int
    invalid: int

    @property
    def verified(self) -> bool:
        return self.invalid == 0


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in (value or []) if item is not None and str(item).strip())


def adapt_legacy_profile(document: dict, tenant_id: str) -> tuple[Profile, ProfileVersion]:
    if document.get("tenant_id") != tenant_id:
        raise ValueError("Legacy ContentProfile is outside migration tenant scope")
    safe = {key: document.get(key) for key in LEGACY_ALLOWLIST if key in document}
    profile_id = str(safe.get("profile_id") or "").strip()
    name = str(safe.get("name") or "").strip()
    version_number = int(safe.get("version") or 1)
    if not profile_id or not name or version_number < 1:
        raise ValueError("Legacy ContentProfile identity/version is invalid")
    deterministic_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    created_at = safe.get("created_at") if isinstance(safe.get("created_at"), datetime) else deterministic_epoch
    updated_at = safe.get("updated_at") if isinstance(safe.get("updated_at"), datetime) else created_at
    audience = _strings(safe.get("audience")) or ("general audience",)
    voice = _strings(safe.get("voice")) or ("professional",)
    setup = ProfileSetup(
        name=name,
        account_type="other",
        goals=("educate",),
        audience=", ".join(audience),
        voice=voice[:6],
        batch_size=4,
        channels=("manual_export",),
    )
    proposal = DeterministicProfileAnalyzer().propose(setup)
    source_json = json.dumps(safe, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    source_digest = hashlib.sha256(source_json.encode("utf-8")).hexdigest()
    payload = {
        "schema_version": 2,
        "profile_id": profile_id,
        "tenant_id": tenant_id,
        "version": version_number,
        "identity": ProfileIdentity(
            name=name,
            account_type="other",
            summary=str(safe.get("positioning") or safe.get("display_name") or proposal.identity_summary),
        ),
        "goals": ("educate",),
        "audience": audience,
        "editorial_strategy": EditorialStrategy(
            topic_families=_strings(safe.get("core_topics")),
            excluded_topics=_strings(safe.get("excluded_topics")),
        ),
        "novelty_policy": NoveltyPolicy(),
        "copy_policy": CopyPolicy(
            voice_traits=voice,
            target_language=safe.get("target_language") if safe.get("target_language") in {"es", "en", "pt"} else "es",
            min_words=safe.get("min_words"),
            max_words=safe.get("max_words"),
        ),
        "claim_policy": ClaimPolicy(
            forbidden_claims=_strings(safe.get("forbidden_claims")),
            safety_sensitivities=_strings(safe.get("brand_constraints")) + _strings(safe.get("banned_phrases")),
        ),
        "visual_system": VisualSystem(traits=_strings([safe.get("default_visual_style")]) if safe.get("visual_enabled", True) else ("disabled",)),
        "publishing_preferences": PublishingPreferences(channels=("manual_export",), default_batch_size=4),
        "agent_policy": AgentPolicy(),
        "inferred_from_examples": (),
        "provenance": MigrationProvenance(
            source="MK0_CONTENT_PROFILE",
            source_profile_id=profile_id,
            source_version=version_number,
            source_digest=source_digest,
        ),
        "accepted_at": updated_at,
        "created_at": created_at,
    }
    provisional = ProfileVersion(**payload, digest="0" * 64)
    version = provisional.model_copy(update={"digest": canonical_digest(provisional)})
    profile = Profile(
        profile_id=profile_id,
        tenant_id=tenant_id,
        current_version=version_number,
        name=name,
        status=ProfileStatus.ARCHIVED if safe.get("archived") else ProfileStatus.ACTIVE,
        created_at=created_at,
        updated_at=updated_at,
    )
    return profile, version


async def migrate_legacy_profiles(db: Any, tenant_id: str) -> ProfileBridgeReport:
    scanned = migrated = existing = invalid = 0
    cursor = db["content_profiles"].find({"tenant_id": tenant_id})
    async for document in cursor:
        scanned += 1
        try:
            profile, version = adapt_legacy_profile(document, tenant_id)
            version_query = {
                "tenant_id": tenant_id,
                "profile_id": profile.profile_id,
                "version": version.version,
            }
            profile_query = {"tenant_id": tenant_id, "profile_id": profile.profile_id}
            stored_version = await db["profile_versions"].find_one(version_query)
            stored_profile = await db["profiles"].find_one(profile_query)

            # A pre-existing Profile without the exact bridge version is an ID
            # collision, not proof that this legacy row was already migrated.
            if stored_profile and not stored_version:
                invalid += 1
                continue
            if stored_version and stored_version.get("digest") != version.digest:
                invalid += 1
                continue
            if stored_profile:
                current_version = int(stored_profile.get("current_version") or 0)
                if current_version < version.version:
                    invalid += 1
                    continue
                if current_version == version.version and stored_profile.get("name") != profile.name:
                    invalid += 1
                    continue

            version_result = await db["profile_versions"].update_one(
                version_query,
                {"$setOnInsert": version.model_dump()},
                upsert=True,
            )
            await db["profiles"].update_one(
                profile_query,
                {"$setOnInsert": profile.model_dump()},
                upsert=True,
            )
            stored = await db["profile_versions"].find_one(version_query)
            stored_profile = await db["profiles"].find_one(profile_query)
            if (
                not stored
                or stored.get("digest") != version.digest
                or not stored_profile
                or int(stored_profile.get("current_version") or 0) < version.version
            ):
                invalid += 1
            elif version_result.upserted_id is None:
                existing += 1
            else:
                migrated += 1
        except (TypeError, ValueError):
            invalid += 1
    return ProfileBridgeReport(MIGRATION_ID, tenant_id, scanned, migrated, existing, invalid)
