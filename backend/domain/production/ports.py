from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from domain.planning.models import ContentPlanV1
from domain.profiles.models import ProfileVersion
from domain.production.models import (
    AgentAttemptEvidenceV1,
    ContentRevisionV1,
    ContentSpecV1,
    EditorialReviewV1,
    GenerationRunV1,
    ResearchPackV1,
)


ArtifactT = TypeVar("ArtifactT")


@dataclass(frozen=True)
class AgentInvocationResult(Generic[ArtifactT]):
    artifact: ArtifactT
    attempts: tuple[AgentAttemptEvidenceV1, ...]


class ResearchAgentPort(Protocol):
    async def research(
        self,
        *,
        tenant_id: str,
        run_id: str,
        plan: ContentPlanV1,
        profile: ProfileVersion,
    ) -> AgentInvocationResult[ResearchPackV1]: ...


class WriterAgentPort(Protocol):
    async def write(
        self,
        *,
        tenant_id: str,
        run_id: str,
        plan: ContentPlanV1,
        profile: ProfileVersion,
        research: ResearchPackV1,
    ) -> AgentInvocationResult[ContentSpecV1]: ...


class EditorAgentPort(Protocol):
    async def edit(
        self,
        *,
        tenant_id: str,
        run_id: str,
        plan: ContentPlanV1,
        profile: ProfileVersion,
        research: ResearchPackV1,
        content: ContentSpecV1,
        revision_cycle: int,
    ) -> AgentInvocationResult[EditorialReviewV1]: ...


class ProductionRepositoryPort(Protocol):
    async def create_run(self, run: GenerationRunV1) -> None: ...

    async def get_run(self, tenant_id: str, run_id: str) -> GenerationRunV1 | None: ...

    async def update_run(self, run: GenerationRunV1) -> None: ...

    async def append_agent_attempt(self, tenant_id: str, run_id: str, attempt: AgentAttemptEvidenceV1) -> None: ...

    async def save_artifact(
        self,
        *,
        tenant_id: str,
        run_id: str,
        artifact_type: str,
        artifact_id: str,
        digest: str,
        payload: dict,
    ) -> None: ...

    async def save_revision(self, revision: ContentRevisionV1) -> None: ...
