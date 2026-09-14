from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileVersionPatch(BaseModel):
    """Allowlisted semantic additions for creating a new immutable ProfileVersion.

    This object never mutates an existing ProfileVersion. It is intentionally
    small so learning/data-quality flows cannot rewrite unrelated profile
    authority by smuggling arbitrary fields through a generic patch document.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    add_topic_families: tuple[str, ...] = Field(default=(), max_length=12)
    add_hook_tendencies: tuple[str, ...] = Field(default=(), max_length=12)

    @field_validator("add_topic_families", "add_hook_tendencies")
    @classmethod
    def normalize_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(item.strip() for item in value if item.strip()))
        if any(len(item) > 240 for item in normalized):
            raise ValueError("profile patch values must be 240 characters or fewer")
        return normalized

    @model_validator(mode="after")
    def require_change(self):
        if not self.add_topic_families and not self.add_hook_tendencies:
            raise ValueError("ProfileVersionPatch must request at least one allowlisted change")
        return self
