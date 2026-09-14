from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from application.profiles.analyzer import _audience_topic_families
from application.profiles.patch_service import ProfilePatchService
from application.profiles.service import AcceptedProfile, ProfileConflict
from domain.profiles.patches import ProfileVersionPatch
from domain.profiles.ports import ProfileRepositoryPort
from domain.profiles.upgrades import (
    HumanProfileUpgradeDecisionV1,
    ProfileUpgradeDecisionValue,
    ProfileUpgradeProposalV1,
    deterministic_profile_upgrade_decision_id,
    deterministic_profile_upgrade_proposal_id,
    malformed_topic_family,
    profile_upgrade_digest,
)


class ProfileUpgradeConflict(RuntimeError):
    pass


class ProfileUpgradeStale(ProfileUpgradeConflict):
    pass


@dataclass(frozen=True)
class ProfileUpgradeDecisionResult:
    decision: HumanProfileUpgradeDecisionV1
    accepted_profile: AcceptedProfile | None


class ProfileUpgradeService:
    """Repair legacy inferred Profile authority without rewriting historical versions."""

    def __init__(self, *, profiles: ProfileRepositoryPort, decisions, profile_patches: ProfilePatchService):
        self.profiles = profiles
        self.decisions = decisions
        self.profile_patches = profile_patches

    @staticmethod
    def proposal_for_version(version) -> ProfileUpgradeProposalV1 | None:
        existing = version.editorial_strategy.topic_families
        malformed = tuple(item for item in existing if malformed_topic_family(item))
        if not malformed:
            return None

        clean = [item for item in existing if item not in malformed]
        audience_text = " ".join(version.audience).strip()
        derived = _audience_topic_families(audience_text, limit=1) if audience_text else ()
        for item in derived:
            if item and item.casefold() not in {value.casefold() for value in clean}:
                clean.append(item)
        proposed = tuple(clean)
        if not proposed:
            raise ProfileUpgradeConflict(
                "Legacy Profile contains malformed topics but current authority is insufficient for a safe normalization"
            )

        proposal_id = deterministic_profile_upgrade_proposal_id(
            profile_id=version.profile_id,
            profile_digest=version.digest,
            proposed_topics=proposed,
        )
        payload = {
            "schema_version": 1,
            "proposal_id": proposal_id,
            "tenant_id": version.tenant_id,
            "profile_id": version.profile_id,
            "profile_version": version.version,
            "profile_digest": version.digest,
            "removed_topic_families": malformed,
            "proposed_topic_families": proposed,
            "reason_codes": ("MALFORMED_TOPIC_FAMILY",),
            "policy_version": "r4-profile-upgrade-v1",
        }
        return ProfileUpgradeProposalV1(
            **payload,
            proposal_digest=profile_upgrade_digest(payload),
        )

    async def propose(self, profile_id: str) -> ProfileUpgradeProposalV1 | None:
        profile = await self.profiles.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        version = await self.profiles.get_version(profile_id, profile.current_version)
        if version is None:
            raise RuntimeError("Current ProfileVersion is unavailable")
        return self.proposal_for_version(version)

    async def decision_for(self, proposal_id: str) -> HumanProfileUpgradeDecisionV1 | None:
        return await self.decisions.get(proposal_id)

    async def decide(
        self,
        *,
        tenant_id: str,
        profile_id: str,
        proposal_digest: str,
        expected_current_version: int,
        decision: ProfileUpgradeDecisionValue,
        now: datetime | None = None,
    ) -> ProfileUpgradeDecisionResult:
        base = await self.profiles.get_version(profile_id, expected_current_version)
        if base is None or base.tenant_id != tenant_id:
            raise LookupError("ProfileVersion not found")
        proposal = self.proposal_for_version(base)
        if proposal is None:
            raise ProfileUpgradeConflict("Current ProfileVersion does not require a legacy upgrade")
        if proposal.proposal_digest != proposal_digest:
            raise ProfileUpgradeConflict("Profile upgrade proposal changed; reload before deciding")

        existing = await self.decisions.get(proposal.proposal_id)
        if existing is not None:
            if (
                existing.decision is not decision
                or existing.expected_current_version != expected_current_version
                or existing.proposal_digest != proposal_digest
            ):
                raise ProfileUpgradeConflict("Profile upgrade proposal already has a different human decision")
            if existing.decision is ProfileUpgradeDecisionValue.REJECTED:
                return ProfileUpgradeDecisionResult(existing, None)
            return ProfileUpgradeDecisionResult(existing, await self._resume_accepted(proposal, existing))

        profile = await self.profiles.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        if profile.current_version != expected_current_version:
            raise ProfileUpgradeStale("Profile changed before upgrade decision could be recorded")

        decided_at = now or datetime.now(timezone.utc)
        target = expected_current_version + 1 if decision is ProfileUpgradeDecisionValue.ACCEPTED else None
        decision_id = deterministic_profile_upgrade_decision_id(
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            decision=decision,
            expected_current_version=expected_current_version,
        )
        payload = {
            "schema_version": 1,
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "profile_id": profile_id,
            "proposal_id": proposal.proposal_id,
            "proposal_digest": proposal.proposal_digest,
            "decision": decision,
            "expected_current_version": expected_current_version,
            "target_profile_version": target,
            "decided_at": decided_at,
        }
        persisted = await self.decisions.append(
            HumanProfileUpgradeDecisionV1(
                **payload,
                decision_digest=profile_upgrade_digest(payload),
            )
        )
        if persisted.decision is ProfileUpgradeDecisionValue.REJECTED:
            return ProfileUpgradeDecisionResult(persisted, None)
        return ProfileUpgradeDecisionResult(persisted, await self._resume_accepted(proposal, persisted))

    async def _resume_accepted(
        self,
        proposal: ProfileUpgradeProposalV1,
        decision: HumanProfileUpgradeDecisionV1,
    ) -> AcceptedProfile:
        if decision.target_profile_version is None:
            raise ProfileUpgradeConflict("Accepted upgrade is missing target ProfileVersion")
        base = await self.profiles.get_version(proposal.profile_id, decision.expected_current_version)
        if base is None or base.digest != proposal.profile_digest:
            raise ProfileUpgradeStale("Legacy upgrade base ProfileVersion is unavailable or changed")
        patch = ProfileVersionPatch(replace_topic_families=proposal.proposed_topic_families)
        expected_target = self.profile_patches.build_version(base, patch, accepted_at=decision.decided_at)

        profile = await self.profiles.get_profile(proposal.profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        if profile.current_version >= decision.target_profile_version:
            target = await self.profiles.get_version(proposal.profile_id, decision.target_profile_version)
            if target is None or target.digest != expected_target.digest:
                raise ProfileUpgradeStale("Target ProfileVersion exists but does not match this upgrade decision")
            return AcceptedProfile(profile, target)
        if profile.current_version != decision.expected_current_version:
            raise ProfileUpgradeStale("Profile changed before legacy upgrade could be applied")

        try:
            accepted = await self.profile_patches.apply(
                tenant_id=proposal.tenant_id,
                profile_id=proposal.profile_id,
                expected_current_version=decision.expected_current_version,
                patch=patch,
                accepted_at=decision.decided_at,
            )
        except ProfileConflict as exc:
            raise ProfileUpgradeStale(str(exc)) from exc
        if accepted.version.version != decision.target_profile_version:
            raise RuntimeError("Legacy upgrade applied to an unexpected ProfileVersion")
        return accepted
