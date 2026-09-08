from __future__ import annotations

from typing import Protocol

from domain.profiles.models import ProfileVersion
from domain.production.models import ContentRevisionV1, GenerationRunV1
from domain.visual.models import DesignProfileV1, VisualSpecV1


class ProfileVersionReaderPort(Protocol):
    async def get_version(self, profile_id: str, version: int) -> ProfileVersion | None: ...


class VisualProductionAuthorityPort(Protocol):
    async def get_run(self, tenant_id: str, run_id: str) -> GenerationRunV1 | None: ...

    async def update_run(self, run: GenerationRunV1) -> None: ...

    async def get_revision(
        self,
        tenant_id: str,
        revision_id: str,
    ) -> ContentRevisionV1 | None: ...

    async def get_artifact(self, tenant_id: str, artifact_id: str) -> dict | None: ...


class VisualRepositoryPort(Protocol):
    async def save_design_profile(self, profile: DesignProfileV1) -> None: ...

    async def get_design_profile(self, design_profile_id: str) -> DesignProfileV1 | None: ...

    async def save_visual_spec(self, spec: VisualSpecV1) -> None: ...

    async def get_visual_spec(self, visual_spec_id: str) -> VisualSpecV1 | None: ...

    async def bind_revision_visual(
        self,
        *,
        revision_id: str,
        expected_visual_spec_ref: str | None,
        visual_spec_ref: str,
        visual_spec_digest: str,
    ) -> ContentRevisionV1 | None: ...
