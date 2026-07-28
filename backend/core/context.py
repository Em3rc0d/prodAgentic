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
