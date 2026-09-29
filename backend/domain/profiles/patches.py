from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileVersionPatch(BaseModel):
    """Allowlisted changes for creating a new immutable ProfileVersion.

    Learning flows normally append bounded values. Data-quality/profile-upgrade
    flows may replace topic families explicitly, but can never combine replacement
    and additions in the same patch or rewrite unrelated Profile authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    add_topic_families: tuple[str, ...] = Field(default=(), max_length=12)
    add_hook_tendencies: tuple[str, ...] = Field(default=(), max_length=12)
    replace_topic_families: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=12)

    @field_validator("add_topic_families", "add_hook_tendencies", "replace_topic_families")
    @classmethod
    def normalize_values(cls, value):
        if value is None:
            return None
        normalized = tuple(dict.fromkeys(item.strip() for item in value if item.strip()))
        if any(len(item) > 240 for item in normalized):
            raise ValueError("profile patch values must be 240 characters or fewer")
        return normalized

    @model_validator(mode="after")
    def require_change(self):
        if self.replace_topic_families is not None and self.add_topic_families:
            raise ValueError("topic replacement and topic additions cannot be combined")
        if (
            not self.add_topic_families
            and not self.add_hook_tendencies
            and self.replace_topic_families is None
        ):
            raise ValueError("ProfileVersionPatch must request at least one allowlisted change")
        return self
