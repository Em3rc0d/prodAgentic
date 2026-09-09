from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


_SHA256 = r"^[0-9a-f]{64}$"
_EXPORT_FILENAME = r"^assets/page-[0-9]{2}\.png$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ManualExportAssetV1(FrozenModel):
    asset_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(pattern=_EXPORT_FILENAME, max_length=64)
    content_type: Literal["image/png"] = "image/png"
    byte_size: int = Field(gt=0, le=16 * 1024 * 1024)
    sha256: str = Field(pattern=_SHA256)


class ManualExportManifestV1(FrozenModel):
    schema_version: Literal[1] = 1
    export_kind: Literal["manual"] = "manual"
    package_format: Literal["zip"] = "zip"
    approval_id: str = Field(min_length=1, max_length=128)
    approval_bundle_sha256: str = Field(pattern=_SHA256)
    content_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    content_spec_id: str = Field(min_length=1, max_length=128)
    content_digest: str = Field(pattern=_SHA256)
    visual_spec_digest: str | None = Field(default=None, pattern=_SHA256)
    qa_digest: str = Field(pattern=_SHA256)
    policy_version: str = Field(min_length=1, max_length=120)
    caption_filename: Literal["caption.txt"] = "caption.txt"
    caption_sha256: str = Field(pattern=_SHA256)
    assets: tuple[ManualExportAssetV1, ...] = ()


def canonical_export_json(payload: BaseModel | dict) -> bytes:
    value = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canonical.encode("utf-8") + b"\n"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
