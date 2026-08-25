from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ContentMemoryKind(str, Enum):
    FINAL_CONTENT = "FINAL_CONTENT"
    PUBLISHED_CONTENT = "PUBLISHED_CONTENT"


class ContentMemoryRecord(BaseModel):
    memory_id: str
    workspace_id: str
    run_id: str
    kind: ContentMemoryKind
    canonicalizer_version: str
    normalized_sha256: str = Field(min_length=64, max_length=64)
    text_preview: str = Field(max_length=500)
    content_status: str
    external_post_urn: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("workspace_id", "run_id", "content_status")
    @classmethod
    def require_non_blank(cls, value: str):
        if not value or not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("normalized_sha256")
    @classmethod
    def require_sha256_hex(cls, value: str):
        normalized = value.lower()
        if any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("normalized_sha256 must be hexadecimal")
        return normalized
