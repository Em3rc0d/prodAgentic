from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from application.profiles.patch_service import ProfilePatchService
from application.profiles.service import AcceptedProfile, ProfileConflict
from domain.learning.models import ConfidenceBand, PerformanceDimension, PerformanceSummaryV1, canonical_sha256
from domain.learning.proposal_ports import LearningProposalRepositoryPort
from domain.learning.proposals import (
    HumanProfileDecisionV1,
    LearningDecisionValue,
    LearningProposalType,
    LearningProposalV1,
    LearningRiskClass,
    deterministic_learning_decision_id,
    deterministic_learning_proposal_id,
)
from domain.profiles.patches import ProfileVersionPatch
from domain.profiles.ports import ProfileRepositoryPort


class LearningProposalConflict(RuntimeError):
    pass


class LearningProposalStale(LearningProposalConflict):
    pass


@dataclass(frozen=True)
class LearningDecisionResult:
    decision: HumanProfileDecisionV1
    accepted_profile: AcceptedProfile | None


def _proposal_digest(payload: dict) -> str:
    return canonical_sha256(payload)


def _decision_digest(payload: dict) -> str:
    return canonical_sha256(payload)


class LearningProposalService:
    """Turn mature performance evidence into bounded, human-governed Profile proposals."""

    min_positive_lift = 0.05
    max_proposals = 6

    def __init__(
        self,
        *,
        summaries,
        proposals: LearningProposalRepositoryPort,
        profiles: ProfileRepositoryPort,
        profile_patches: ProfilePatchService,
    ):
        self.summaries = summaries
        self.proposals = proposals
        self.profiles = profiles
        self.profile_patches = profile_patches

    async def rebuild(self, profile_id: str) -> tuple[LearningProposalV1, ...]:
        profile = await self.profiles.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        version = await self.profiles.get_version(profile_id, profile.current_version)
        if version is None:
            raise RuntimeError("Current ProfileVersion is unavailable")

        summary: PerformanceSummaryV1 = await self.summaries.rebuild(profile_id)
        if summary.tenant_id != version.tenant_id or summary.profile_id != version.profile_id:
            raise LearningProposalConflict("Performance summary scope does not match Profile authority")

        ranked = sorted(
            (
                signal
                for signal in summary.signals
                if signal.confidence in {ConfidenceBand.MEDIUM, ConfidenceBand.HIGH}
                and signal.planner_weight > 0
                and signal.lift >= self.min_positive_lift
                and signal.dimension in {
                    PerformanceDimension.CANONICAL_TOPIC,
                    PerformanceDimension.HOOK_PATTERN,
                }
            ),
            key=lambda item: (-item.planner_weight, -item.lift, item.dimension.value, item.key),
        )

        existing_topics = {item.casefold() for item in version.editorial_strategy.topic_families}
        existing_hooks = {item.casefold() for item in version.copy_policy.hook_tendencies}
        produced: list[LearningProposalV1] = []
        for signal in ranked:
            value = signal.key.strip()
            if not value:
                continue
            if signal.dimension is PerformanceDimension.CANONICAL_TOPIC:
                if value.casefold() in existing_topics:
                    continue
                proposal_type = LearningProposalType.PROMOTE_TOPIC_FAMILY
                risk_class = LearningRiskClass.SEMANTIC
                rationale = (
                    f"This topic has a positive repeated association across {signal.sample_size} mature publication(s). "
                    "Promoting it changes Profile strategy and therefore requires explicit human acceptance."
                )
            else:
                if value.casefold() in existing_hooks:
                    continue
                proposal_type = LearningProposalType.PREFER_HOOK_TENDENCY
                risk_class = LearningRiskClass.OPERATIONAL
                rationale = (
                    f"This hook pattern has a positive repeated association across {signal.sample_size} mature publication(s). "
                    "The proposal remains subordinate to novelty, quality and human Profile authority."
                )

            proposal_id = deterministic_learning_proposal_id(
                tenant_id=version.tenant_id,
                profile_id=version.profile_id,
                profile_digest=version.digest,
                summary_digest=summary.summary_digest,
                proposal_type=proposal_type,
                proposed_value=value,
            )
            payload = {
                "schema_version": 1,
                "proposal_id": proposal_id,
                "tenant_id": version.tenant_id,
                "profile_id": version.profile_id,
                "profile_version": version.version,
                "profile_digest": version.digest,
                "summary_id": summary.summary_id,
                "summary_digest": summary.summary_digest,
                "signal_id": signal.signal_id,
                "proposal_type": proposal_type,
                "dimension": signal.dimension,
                "proposed_value": value,
                "rationale": rationale,
                "confidence": signal.confidence,
                "sample_size": signal.sample_size,
                "lift": signal.lift,
                "risk_class": risk_class,
                "state": "PROPOSED",
                "policy_version": "r4-learning-proposal-v1",
                "created_at": summary.created_at,
            }
            proposal = LearningProposalV1(
                **payload,
                proposal_digest=_proposal_digest(payload),
            )
            produced.append(await self.proposals.append(proposal))
            if len(produced) >= self.max_proposals:
                break
        return tuple(produced)

    async def list_for_profile(self, profile_id: str) -> list[LearningProposalV1]:
        profile = await self.profiles.get_profile(profile_id)
        if profile is None:
            raise LookupError("Profile not found")
        return await self.proposals.list_for_profile(profile_id)

    async def decision_for(self, proposal_id: str) -> HumanProfileDecisionV1 | None:
        return await self.proposals.get_decision(proposal_id)

    async def decide(
        self,
        *,
        tenant_id: str,
        profile_id: str,
        proposal_id: str,
        proposal_digest: str,
        expected_current_version: int,
        decision: LearningDecisionValue,
        now: datetime | None = None,
    ) -> LearningDecisionResult:
        proposal = await self.proposals.get(proposal_id)
        if proposal is None or proposal.profile_id != profile_id or proposal.tenant_id != tenant_id:
            raise LookupError("Learning proposal not found")
        if proposal.proposal_digest != proposal_digest:
            raise LearningProposalConflict("Learning proposal changed; reload before deciding")
        if expected_current_version != proposal.profile_version:
            raise LearningProposalStale("Learning proposal is bound to a different ProfileVersion")

        existing = await self.proposals.get_decision(proposal_id)
        if existing is not None:
            if (
                existing.decision is not decision
                or existing.expected_current_version != expected_current_version
                or existing.proposal_digest != proposal_digest
            ):
                raise LearningProposalConflict("Learning proposal already has a different human decision")
            if existing.decision is LearningDecisionValue.REJECTED:
                return LearningDecisionResult(existing, None)
            accepted = await self._resume_accepted(proposal, existing)
            return LearningDecisionResult(existing, accepted)

        if decision is LearningDecisionValue.ACCEPTED:
            current_profile = await self.profiles.get_profile(profile_id)
            if current_profile is None:
                raise LookupError("Profile not found")
            if current_profile.current_version != expected_current_version:
                raise LearningProposalStale("Profile changed before learning decision could be accepted")

        decided_at = now or datetime.now(timezone.utc)
        target = expected_current_version + 1 if decision is LearningDecisionValue.ACCEPTED else None
        decision_id = deterministic_learning_decision_id(
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
        persisted = await self.proposals.append_decision(
            HumanProfileDecisionV1(**payload, decision_digest=_decision_digest(payload))
        )
        if persisted.decision is LearningDecisionValue.REJECTED:
            return LearningDecisionResult(persisted, None)
        accepted = await self._resume_accepted(proposal, persisted)
        return LearningDecisionResult(persisted, accepted)

    async def _resume_accepted(
        self,
        proposal: LearningProposalV1,
        decision: HumanProfileDecisionV1,
    ) -> AcceptedProfile:
        if decision.target_profile_version is None:
            raise LearningProposalConflict("Accepted decision is missing target ProfileVersion")

        profile = await self.profiles.get_profile(proposal.profile_id)
        if profile is None:
            raise LookupError("Profile not found")

        if proposal.proposal_type is LearningProposalType.PROMOTE_TOPIC_FAMILY:
            patch = ProfileVersionPatch(add_topic_families=(proposal.proposed_value,))
        elif proposal.proposal_type is LearningProposalType.PREFER_HOOK_TENDENCY:
            patch = ProfileVersionPatch(add_hook_tendencies=(proposal.proposed_value,))
        else:
            raise LearningProposalConflict("Unsupported learning proposal type")

        base = await self.profiles.get_version(
            proposal.profile_id,
            decision.expected_current_version,
        )
        if base is None or base.digest != proposal.profile_digest:
            raise LearningProposalStale("Learning proposal base ProfileVersion is unavailable or changed")
        expected_target = self.profile_patches.build_version(
            base,
            patch,
            accepted_at=decision.decided_at,
        )

        if profile.current_version >= decision.target_profile_version:
            target = await self.profiles.get_version(
                proposal.profile_id,
                decision.target_profile_version,
            )
            if target is None:
                raise RuntimeError("Learning decision target ProfileVersion is unavailable")
            if target.digest != expected_target.digest:
                raise LearningProposalStale(
                    "Target ProfileVersion exists but does not match this learning decision"
                )
            return AcceptedProfile(profile, target)

        if profile.current_version != decision.expected_current_version:
            raise LearningProposalStale("Profile changed before learning decision could be applied")

        try:
            accepted = await self.profile_patches.apply(
                tenant_id=proposal.tenant_id,
                profile_id=proposal.profile_id,
                expected_current_version=decision.expected_current_version,
                patch=patch,
                accepted_at=decision.decided_at,
            )
        except ProfileConflict as exc:
            raise LearningProposalStale(str(exc)) from exc
        if accepted.version.version != decision.target_profile_version:
            raise RuntimeError("Learning decision applied to an unexpected ProfileVersion")
        return accepted
