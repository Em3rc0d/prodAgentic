from __future__ import annotations

from typing import Protocol

from .proposals import HumanProfileDecisionV1, LearningProposalV1


class LearningProposalRepositoryPort(Protocol):
    async def append(self, proposal: LearningProposalV1) -> LearningProposalV1: ...

    async def get(self, proposal_id: str) -> LearningProposalV1 | None: ...

    async def list_for_profile(self, profile_id: str) -> list[LearningProposalV1]: ...

    async def append_decision(self, decision: HumanProfileDecisionV1) -> HumanProfileDecisionV1: ...

    async def get_decision(self, proposal_id: str) -> HumanProfileDecisionV1 | None: ...
