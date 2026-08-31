from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuickSourcePacketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=1000)
    facts: list[str] = Field(min_length=1, max_length=25)
    strict_mode: bool = True

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("facts")
    @classmethod
    def normalize_facts(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for fact in value:
            fact = fact.strip()
            if not fact:
                raise ValueError("facts must not contain blank values")
            if len(fact) > 1000:
                raise ValueError("each fact must be at most 1000 characters")
            normalized.append(fact)
        if len(normalized) != len(set(normalized)):
            raise ValueError("facts must be unique")
        return normalized


class SourcePacketSummary(BaseModel):
    packet_id: str
    title: str
    summary: str | None = None
    strict_mode: bool
    evidence_count: int
    allowed_fact_count: int
    allowed_inference_count: int
    created_at: datetime


class SourcePacketListResponse(BaseModel):
    packets: list[SourcePacketSummary]
    count: int
