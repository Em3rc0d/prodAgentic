from dataclasses import dataclass
from uuid import uuid4

from domain.profiles.models import (
    AgentPolicy,
    ClaimPolicy,
    CopyPolicy,
    EditorialStrategy,
    MigrationProvenance,
    NoveltyPolicy,
    Profile,
    ProfileIdentity,
    ProfileInferenceProposal,
    ProfileSetup,
    ProfileStatus,
    ProfileVersion,
    PublishingPreferences,
    VisualSystem,
    canonical_digest,
    utc_now,
)
from domain.profiles.ports import ProfileAnalyzerPort, ProfileRepositoryPort


class ProfileConflict(RuntimeError):
    pass


class ProposalMismatch(ValueError):
    pass


@dataclass(frozen=True)
class AcceptedProfile:
    profile: Profile
    version: ProfileVersion


class ProfileService:
    def __init__(self, repository: ProfileRepositoryPort, analyzer: ProfileAnalyzerPort):
        self.repository = repository
        self.analyzer = analyzer

    def propose(self, setup: ProfileSetup) -> ProfileInferenceProposal:
        return self.analyzer.propose(setup)

    def _version(
        self,
        *,
        profile_id: str,
        tenant_id: str,
        version: int,
        setup: ProfileSetup,
        proposal: ProfileInferenceProposal,
    ) -> ProfileVersion:
        now = utc_now()
        payload = {
            "schema_version": 2,
            "profile_id": profile_id,
            "tenant_id": tenant_id,
            "version": version,
            "identity": ProfileIdentity(
                name=setup.name,
                account_type=setup.account_type,
                summary=proposal.identity_summary,
            ),
            "goals": setup.goals,
            "audience": proposal.audience_segments,
            "editorial_strategy": EditorialStrategy(topic_families=proposal.topic_families),
            "novelty_policy": NoveltyPolicy(),
            "copy_policy": CopyPolicy(
                voice_traits=setup.voice,
                nuance=setup.voice_nuance,
                caption_length_tendency=proposal.caption_length_tendency,
                hook_tendencies=proposal.hook_tendencies,
                cta_style=proposal.cta_style,
            ),
            "claim_policy": ClaimPolicy(),
            "visual_system": VisualSystem(),
            "publishing_preferences": PublishingPreferences(
                channels=setup.channels,
                default_batch_size=setup.batch_size,
            ),
            "agent_policy": AgentPolicy(),
            "inferred_from_examples": proposal.evidence,
            "provenance": MigrationProvenance(source="USER_ACCEPTED"),
            "accepted_at": now,
            "created_at": now,
        }
        provisional = ProfileVersion(**payload, digest="0" * 64)
        return provisional.model_copy(update={"digest": canonical_digest(provisional)})

    def _verify(self, setup: ProfileSetup, expected_digest: str) -> ProfileInferenceProposal:
        proposal = self.propose(setup)
        if proposal.proposal_digest != expected_digest:
            raise ProposalMismatch("Inference proposal no longer matches the accepted setup")
        return proposal

    async def create(self, tenant_id: str, setup: ProfileSetup, expected_digest: str) -> AcceptedProfile:
        proposal = self._verify(setup, expected_digest)
        now = utc_now()
        profile = Profile(
            profile_id=str(uuid4()), tenant_id=tenant_id, current_version=1,
            name=setup.name, status=ProfileStatus.ACTIVE, created_at=now, updated_at=now,
        )
        version = self._version(
            profile_id=profile.profile_id, tenant_id=tenant_id, version=1,
            setup=setup, proposal=proposal,
        )
        await self.repository.create(profile, version)
        return AcceptedProfile(profile, version)

    async def update(
        self,
        tenant_id: str,
        profile_id: str,
        expected_current_version: int,
        setup: ProfileSetup,
        expected_digest: str,
    ) -> AcceptedProfile:
        existing = await self.repository.get_profile(profile_id)
        if existing is None:
            raise LookupError("Profile not found")
        if existing.tenant_id != tenant_id or existing.current_version != expected_current_version:
            raise ProfileConflict("Profile version changed; reload before accepting another update")
        proposal = self._verify(setup, expected_digest)
        next_version = expected_current_version + 1
        updated = Profile(
            **existing.model_dump(exclude={"current_version", "name", "updated_at"}),
            current_version=next_version,
            name=setup.name,
            updated_at=utc_now(),
        )
        version = self._version(
            profile_id=profile_id, tenant_id=tenant_id, version=next_version,
            setup=setup, proposal=proposal,
        )
        if not await self.repository.append_version(updated, version, expected_current_version):
            raise ProfileConflict("Profile version changed; reload before accepting another update")
        return AcceptedProfile(updated, version)
