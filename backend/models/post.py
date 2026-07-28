from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class PostStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class Performance(BaseModel):
    likes: int = 0
    impressions: int = 0
    comments: int = 0


class Post(BaseModel):
    topic: str
    style: str
    idea: str
    research_output: str
    draft_content: str
    final_content: str
    status: PostStatus = PostStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    performance: Performance = Field(default_factory=Performance)


class IdeasRequest(BaseModel):
    topic: str
    style: str = "educational"
    target_language: str = "es"
    image_prompt_language: str = "en"


class PipelineRequest(BaseModel):
    idea: str
    topic: str
    style: str = "educational"
    target_language: str = "es"
    image_prompt_language: str = "en"
