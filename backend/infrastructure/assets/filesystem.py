from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4

from core.assets import get_asset_root
from domain.rendering.ports import AssetStorePortError, StoredBytes


_MAX_ASSET_BYTES = 16 * 1024 * 1024


class FilesystemAssetStore:
    """Filesystem-first AssetStore rooted at PRODAGENTIC_ASSET_ROOT.

    Storage keys are generated internally from hashed authority identifiers.
    Callers never supply filesystem paths.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or get_asset_root()).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "renders").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _segment(value: str, *, length: int) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]

    def _generated_key(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        render_id: str,
        page_index: int,
        content_type: str,
    ) -> str:
        if content_type != "image/png":
            raise AssetStorePortError("filesystem AssetStore currently accepts image/png only")
        if not 0 <= page_index <= 19:
            raise AssetStorePortError("page_index outside certified range")
        return (
            f"renders/t-{self._segment(tenant_id, length=16)}/"
            f"r-{self._segment(revision_id, length=24)}/"
            f"x-{self._segment(render_id, length=24)}/page-{page_index:02d}.png"
        )

    @staticmethod
    def _validate_storage_key(storage_key: str) -> tuple[str, ...]:
        if not storage_key or "\\" in storage_key:
            raise AssetStorePortError("invalid AssetStore key")
        path = PurePosixPath(storage_key)
        if path.is_absolute():
            raise AssetStorePortError("absolute AssetStore key rejected")
        parts = path.parts
        if not parts or parts[0] != "renders" or any(part in {"", ".", ".."} for part in parts):
            raise AssetStorePortError("AssetStore traversal key rejected")
        return parts

    def _path_for(self, storage_key: str, *, create_parent: bool = False) -> Path:
        parts = self._validate_storage_key(storage_key)
        candidate = self.root.joinpath(*parts)
        parent = candidate.parent
        if create_parent:
            parent.mkdir(parents=True, exist_ok=True)

        cursor = self.root
        for part in parts[:-1]:
            cursor = cursor / part
            if cursor.exists() and cursor.is_symlink():
                raise AssetStorePortError("AssetStore symlink component rejected")

        root_real = self.root.resolve()
        parent_real = parent.resolve()
        try:
            parent_real.relative_to(root_real)
        except ValueError as exc:
            raise AssetStorePortError("AssetStore path escaped configured root") from exc
        if candidate.exists() and candidate.is_symlink():
            raise AssetStorePortError("AssetStore symlink file rejected")
        return candidate

    async def put(
        self,
        data: bytes,
        *,
        tenant_id: str,
        revision_id: str,
        render_id: str,
        page_index: int,
        content_type: str,
    ) -> StoredBytes:
        return await asyncio.to_thread(
            self._put_sync,
            data,
            tenant_id=tenant_id,
            revision_id=revision_id,
            render_id=render_id,
            page_index=page_index,
            content_type=content_type,
        )

    def _put_sync(
        self,
        data: bytes,
        *,
        tenant_id: str,
        revision_id: str,
        render_id: str,
        page_index: int,
        content_type: str,
    ) -> StoredBytes:
        if not data:
            raise AssetStorePortError("refusing to persist empty asset bytes")
        if len(data) > _MAX_ASSET_BYTES:
            raise AssetStorePortError("asset exceeds certified byte-size limit")

        storage_key = self._generated_key(
            tenant_id=tenant_id,
            revision_id=revision_id,
            render_id=render_id,
            page_index=page_index,
            content_type=content_type,
        )
        digest = hashlib.sha256(data).hexdigest()
        target = self._path_for(storage_key, create_parent=True)

        if target.exists():
            existing = target.read_bytes()
            existing_digest = hashlib.sha256(existing).hexdigest()
            if existing_digest != digest:
                raise AssetStorePortError("deterministic AssetStore identity collision")
            return StoredBytes(storage_key=storage_key, sha256=existing_digest, byte_size=len(existing))

        temp = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with temp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
            try:
                directory_fd = os.open(str(target.parent), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)

        owned = target.read_bytes()
        owned_digest = hashlib.sha256(owned).hexdigest()
        if owned_digest != digest or owned != data:
            raise AssetStorePortError("AssetStore read-back verification failed")
        return StoredBytes(storage_key=storage_key, sha256=owned_digest, byte_size=len(owned))

    async def get(self, storage_key: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, storage_key)

    def _get_sync(self, storage_key: str) -> bytes:
        path = self._path_for(storage_key)
        if not path.is_file():
            raise AssetStorePortError("asset bytes are unavailable")
        return path.read_bytes()

    async def exists(self, storage_key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, storage_key)

    def _exists_sync(self, storage_key: str) -> bool:
        try:
            return self._path_for(storage_key).is_file()
        except AssetStorePortError:
            return False

    async def verify(self, storage_key: str, expected_sha256: str) -> bool:
        return await asyncio.to_thread(self._verify_sync, storage_key, expected_sha256)

    def _verify_sync(self, storage_key: str, expected_sha256: str) -> bool:
        if len(expected_sha256) != 64:
            return False
        try:
            data = self._get_sync(storage_key)
        except AssetStorePortError:
            return False
        return hashlib.sha256(data).hexdigest() == expected_sha256

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._delete_sync, storage_key)

    def _delete_sync(self, storage_key: str) -> None:
        path = self._path_for(storage_key)
        if path.exists():
            path.unlink()
