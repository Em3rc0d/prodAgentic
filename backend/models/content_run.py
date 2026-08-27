from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


class MemoryCandidateSnapshot(BaseModel):
    memory_id: str
    run_id: str
    content_status: str
    external_post_urn: Optional[str] = None
    text_preview: str = Field(max_length=500)


class MemoryCheckSnapshot(BaseModel):
    status: str
    outcome: str
    checked_at: datetime
    canonicalizer_version: str
    normalized_sha256: str
    final_memory_id: Optional[str] = None
    candidates: list[MemoryCandidateSnapshot] = Field(default_factory=list, max_length=3)
    error_message: Optional[str] = None
    published_memory_id: Optional[str] = None
    published_index_status: Optional[str] = None
    published_indexed_at: Optional[datetime] = None


class VisualArtifactSnapshot(BaseModel):
    render_id: str
    status: str
    provider: str
    asset_url: Optional[str] = None
    asset_sha256: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    prompt_used: str
    requested_prompt: str
    aspect_ratio: str
    style: str
    idempotency_key: str
    error_message: Optional[str] = None
    rendered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalSnapshot(BaseModel):
    approval_id: str
    approved_at: datetime
    source: str = "explicit_user_action"
    include_visual: bool
    final_content: str
    final_content_sha256: str
    visual_render: Optional[VisualArtifactSnapshot] = None
    visual_render_sha256: Optional[str] = None
    bundle_sha256: str


class PublicationSnapshot(BaseModel):
    provider: str = "linkedin"
    status: str
    attempt_id: str
    approval_id: str
    bundle_sha256: str
    content_sha256: Optional[str] = None
    dedupe_key: Optional[str] = None
    author_urn: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    external_post_urn: Optional[str] = None
    external_image_urn: Optional[str] = None
    error_message: Optional[str] = None
    failure_retry_safety: Optional[str] = None
    failure_phase: Optional[str] = None


class ScheduleSnapshot(BaseModel):
    schedule_id: str
    status: str = "SCHEDULED"
    scheduled_for: datetime
    approval_id: str
    bundle_sha256: str
    created_at: datetime
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ContentRun(BaseModel):
    run_id: str
    topic: str
    style: str
    idea: str
    workspace_id: str = "legacy-default"
    status: ContentRunStatus = ContentRunStatus.GENERATING
    content_profile_id: Optional[str] = None
    content_profile_snapshot: Optional[dict] = None
    requested_target_language: Optional[str] = None
    resolved_target_language: Optional[str] = None
    image_prompt_language: Optional[str] = None
    stages: dict[str, StageSnapshot] = Field(default_factory=dict)
    final_status: Optional[str] = None
    final_content: Optional[str] = None
    visual_prompt: Optional[str] = None
    visual_render: Optional[VisualArtifactSnapshot] = None
    memory_check: Optional[MemoryCheckSnapshot] = None
    approval: Optional[ApprovalSnapshot] = None
    schedule: Optional[ScheduleSnapshot] = None
    publication: Optional[PublicationSnapshot] = None
    post_id: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentRunEditRequest(BaseModel):
    final_content: Optional[str] = Field(default=None, min_length=1)
    visual_prompt: Optional[str] = None

    @model_validator(mode="after")
    def validate_review_edit(self):
        if self.final_content is None and self.visual_prompt is None:
            raise ValueError("At least one editable field must be provided")
        if self.final_content is not None and not self.final_content.strip():
            raise ValueError("Final content cannot be blank")
        return self


class ContentRunApprovalRequest(BaseModel):
    include_visual: bool


class ContentRunScheduleRequest(BaseModel):
    scheduled_for: datetime

    @field_validator("scheduled_for")
    @classmethod
    def require_timezone(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_for must include an explicit timezone offset")
        return value.astimezone(timezone.utc)
