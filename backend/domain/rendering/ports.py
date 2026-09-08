from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.production.models import ContentRevisionV1, GenerationFailureV1, GenerationRunV1
from domain.rendering.models import AssetV1, RendererRequestV1, RenderResultV1


class RendererPortError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AssetStorePortError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class RenderedPageBytes:
    page_id: str
    page_index: int
    width: int
    height: int
    content_type: str
    data: bytes


@dataclass(frozen=True)
class StoredBytes:
    storage_key: str
    sha256: str
    byte_size: int


class RendererPort(Protocol):
    name: str
    version: str

    async def render(self, request: RendererRequestV1) -> tuple[RenderedPageBytes, ...]: ...


class AssetStorePort(Protocol):
    async def put(
        self,
        data: bytes,
        *,
        tenant_id: str,
        revision_id: str,
        render_id: str,
        page_index: int,
        content_type: str,
    ) -> StoredBytes: ...

    async def get(self, storage_key: str) -> bytes: ...

    async def exists(self, storage_key: str) -> bool: ...

    async def verify(self, storage_key: str, expected_sha256: str) -> bool: ...

    async def delete(self, storage_key: str) -> None: ...


class RenderingRepositoryPort(Protocol):
    async def get_asset(self, asset_id: str) -> AssetV1 | None: ...

    async def save_asset(self, asset: AssetV1) -> None: ...

    async def get_render_result(self, render_id: str) -> RenderResultV1 | None: ...

    async def save_render_result(self, result: RenderResultV1) -> None: ...

    async def claim_run_rendering(
        self,
        *,
        run_id: str,
        visual_spec_ref: str,
    ) -> GenerationRunV1 | None: ...

    async def finish_run_qa(
        self,
        *,
        run_id: str,
        visual_spec_ref: str,
    ) -> GenerationRunV1 | None: ...

    async def mark_run_failed(
        self,
        *,
        run_id: str,
        visual_spec_ref: str,
        failure: GenerationFailureV1,
    ) -> GenerationRunV1 | None: ...

    async def bind_revision_assets(
        self,
        *,
        revision_id: str,
        visual_spec_ref: str,
        visual_spec_digest: str,
        expected_asset_refs: tuple[str, ...],
        asset_refs: tuple[str, ...],
    ) -> ContentRevisionV1 | None: ...
