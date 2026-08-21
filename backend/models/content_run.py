from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContentRunStatus(str, Enum):
    GENERATING = "GENERATING"
    TEXT_READY = "TEXT_READY"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StageSnapshot(BaseModel):
    status: StageStatus = StageStatus.PENDING
    output: Optional[str] = None
    selected_model: Optional[str] = None
    provider: Optional[str] = None
    attempt_failures: int = 0
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ContentRun(BaseModel):
    run_id: str
    topic: str
    style: str
    idea: str
    status: ContentRunStatus = ContentRunStatus.GENERATING
    requested_target_language: Optional[str] = None
    resolved_target_language: Optional[str] = None
    image_prompt_language: Optional[str] = None
    stages: dict[str, StageSnapshot] = Field(default_factory=dict)
    final_status: Optional[str] = None
    final_content: Optional[str] = None
    visual_prompt: Optional[str] = None
    post_id: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
