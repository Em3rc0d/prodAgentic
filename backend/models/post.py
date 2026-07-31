from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class PublicationState(str, Enum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class Performance(BaseModel):
    likes: int = 0
    impressions: int = 0
    comments: int = 0


class Source(BaseModel):
    id: str
    url: str
    domain: str
    title: str


class Evidence(BaseModel):
    id: str
    source_id: str
    quote: str
    context: Optional[str] = None


class Claim(BaseModel):
    id: str
    statement: str
    evidence_id: str


class Post(BaseModel):
    topic: str
    style: str
    idea: str
    research_output: str
    draft_content: str
    final_content: str
    status: PublicationState = PublicationState.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    performance: Performance = Field(default_factory=Performance)
    sources: list[Source] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    unsupported_claims_flag: bool = False


from core.context import LanguageCode, TargetLanguageCode, ImagePromptLanguageCode

class IdeasRequest(BaseModel):
    topic: str
    style: str = "educational"
    target_language: TargetLanguageCode = TargetLanguageCode.ES
    image_prompt_language: ImagePromptLanguageCode = ImagePromptLanguageCode.EN


class PipelineRequest(BaseModel):
    idea: str
    topic: str
    style: str = "educational"
    target_language: TargetLanguageCode = TargetLanguageCode.ES
    image_prompt_language: ImagePromptLanguageCode = ImagePromptLanguageCode.EN
