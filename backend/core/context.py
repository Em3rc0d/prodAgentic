import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LanguageCode(Enum):
    AUTO = "auto"
    ES = "es"
    EN = "en"
    PT = "pt"
    UNKNOWN = "unknown"


class TargetLanguageCode(str, Enum):
    """Language code for the post target audience language. AUTO means detect from topic."""
    AUTO = "auto"
    ES = "es"
    EN = "en"
    PT = "pt"

    def to_language_code(self) -> "LanguageCode":
        return LanguageCode(self.value) if self.value != "auto" else LanguageCode.AUTO


class ImagePromptLanguageCode(str, Enum):
    """Language code for image prompt generation. Always explicit, no AUTO."""
    ES = "es"
    EN = "en"
    PT = "pt"

    def to_language_code(self) -> "LanguageCode":
        return LanguageCode(self.value)


@dataclass(frozen=True)
class GenerationContext:
    run_id: str
    workspace_id: str
    topic: str
    style: str
    requested_source_language: LanguageCode
    detected_source_language: LanguageCode
    source_detection_confidence: float
    requested_target_language: LanguageCode
    resolved_target_language: LanguageCode
    image_prompt_language: LanguageCode
    created_at: float = field(default_factory=time.time)
    audience: Optional[str] = None
    content_profile_id: Optional[str] = None
    content_profile_snapshot: Optional[dict] = None

    def profile_instructions(self) -> str:
        profile = self.content_profile_snapshot
        if not profile:
            return ""

        def joined(key: str) -> str:
            values = profile.get(key) or []
            return ", ".join(str(value) for value in values if str(value).strip())

        lines = ["CONTENT PROFILE — follow these constraints for this run:"]
        if profile.get("display_name") or profile.get("name"):
            lines.append(f"Identity: {profile.get('display_name') or profile.get('name')}")
        if profile.get("positioning"):
            lines.append(f"Positioning: {profile['positioning']}")
        if joined("audience"):
            lines.append(f"Audience: {joined('audience')}")
        if joined("voice"):
            lines.append(f"Voice: {joined('voice')}")
        if joined("core_topics"):
            lines.append(f"Core topics: {joined('core_topics')}")
        if joined("excluded_topics"):
            lines.append(f"Excluded topics: {joined('excluded_topics')}")
        if profile.get("min_words") and profile.get("max_words"):
            lines.append(f"Preferred post length: {profile['min_words']}–{profile['max_words']} words")
        if joined("forbidden_claims"):
            lines.append(f"Forbidden claims: {joined('forbidden_claims')}")
        if joined("banned_phrases"):
            lines.append(f"Banned phrases: {joined('banned_phrases')}")
        if joined("brand_constraints"):
            lines.append(f"Brand constraints: {joined('brand_constraints')}")
        lines.append("Do not invent evidence, metrics, credentials, customers, results, or personal experiences.")
        return "\n".join(lines)
