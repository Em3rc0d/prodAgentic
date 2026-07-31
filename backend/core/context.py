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
