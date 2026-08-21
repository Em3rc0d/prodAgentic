from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ContentProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    display_name: Optional[str] = Field(default=None, max_length=120)
    positioning: Optional[str] = Field(default=None, max_length=500)
    audience: list[str] = Field(default_factory=list, max_length=20)
    voice: list[str] = Field(default_factory=list, max_length=20)
    core_topics: list[str] = Field(default_factory=list, max_length=50)
    excluded_topics: list[str] = Field(default_factory=list, max_length=50)
    target_language: str = Field(default="es", pattern="^(es|en|pt)$")
    image_prompt_language: str = Field(default="en", pattern="^(es|en|pt)$")
    min_words: int = Field(default=150, ge=40, le=1000)
    max_words: int = Field(default=220, ge=40, le=1200)
    preferred_style: str = Field(default="educational", max_length=40)
    visual_enabled: bool = True
    default_aspect_ratio: str = Field(default="16:9", pattern="^(16:9|1:1|4:5)$")
    default_visual_style: str = Field(default="", max_length=40)
    forbidden_claims: list[str] = Field(default_factory=list, max_length=50)
    banned_phrases: list[str] = Field(default_factory=list, max_length=100)
    brand_constraints: list[str] = Field(default_factory=list, max_length=100)
    is_default: bool = False

    @model_validator(mode="after")
    def validate_word_range(self):
        if self.min_words > self.max_words:
            raise ValueError("min_words cannot exceed max_words")
        return self


class ContentProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    display_name: Optional[str] = Field(default=None, max_length=120)
    positioning: Optional[str] = Field(default=None, max_length=500)
    audience: Optional[list[str]] = Field(default=None, max_length=20)
    voice: Optional[list[str]] = Field(default=None, max_length=20)
    core_topics: Optional[list[str]] = Field(default=None, max_length=50)
    excluded_topics: Optional[list[str]] = Field(default=None, max_length=50)
    target_language: Optional[str] = Field(default=None, pattern="^(es|en|pt)$")
    image_prompt_language: Optional[str] = Field(default=None, pattern="^(es|en|pt)$")
    min_words: Optional[int] = Field(default=None, ge=40, le=1000)
    max_words: Optional[int] = Field(default=None, ge=40, le=1200)
    preferred_style: Optional[str] = Field(default=None, max_length=40)
    visual_enabled: Optional[bool] = None
    default_aspect_ratio: Optional[str] = Field(default=None, pattern="^(16:9|1:1|4:5)$")
    default_visual_style: Optional[str] = Field(default=None, max_length=40)
    forbidden_claims: Optional[list[str]] = Field(default=None, max_length=50)
    banned_phrases: Optional[list[str]] = Field(default=None, max_length=100)
    brand_constraints: Optional[list[str]] = Field(default=None, max_length=100)
    is_default: Optional[bool] = None
    archived: Optional[bool] = None


class ContentProfile(ContentProfileCreate):
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    archived: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict:
        return self.model_dump(mode="json")
