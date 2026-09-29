from __future__ import annotations

from pathlib import Path

from domain.rendering.ports import AssetStorePortError
from infrastructure.assets.filesystem import FilesystemAssetStore


class R4FilesystemAssetStore(FilesystemAssetStore):
    """R4 AssetStore extension for generated source PNG/JPEG/WebP bytes.

    The same path traversal, symlink, byte-size, atomic write and read-back hash
    guarantees from FilesystemAssetStore remain in force. Final Chromium renders
    continue to be PNG; only pre-composite source assets may use JPEG/WebP.
    """

    _EXTENSIONS = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }

    def __init__(self, root: Path | str | None = None):
        super().__init__(root)

    def _generated_key(
        self,
        *,
        tenant_id: str,
        revision_id: str,
        render_id: str,
        page_index: int,
        content_type: str,
    ) -> str:
        extension = self._EXTENSIONS.get(content_type)
        if extension is None:
            raise AssetStorePortError("R4 AssetStore accepts only PNG/JPEG/WebP images")
        if not 0 <= page_index <= 19:
            raise AssetStorePortError("page_index outside certified range")
        return (
            f"renders/t-{self._segment(tenant_id, length=16)}/"
            f"r-{self._segment(revision_id, length=24)}/"
            f"x-{self._segment(render_id, length=24)}/page-{page_index:02d}.{extension}"
        )
