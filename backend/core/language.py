from lingua import LanguageDetectorBuilder, Language
from core.context import LanguageCode
from dataclasses import dataclass
from typing import Optional

@dataclass
class LanguageDetectionResult:
    language: LanguageCode
    confidence: float
    runner_up_language: Optional[LanguageCode]
    runner_up_confidence: float
    margin: float
    analyzable_characters: int

class LanguageDetectorPort:
    def __init__(self):
        self.detector = (
            LanguageDetectorBuilder
            .from_languages(
                Language.SPANISH,
                Language.ENGLISH,
                Language.PORTUGUESE,
            )
            .with_preloaded_language_models()
            .build()
        )
        self._lang_map = {
            Language.SPANISH: LanguageCode.ES,
            Language.ENGLISH: LanguageCode.EN,
            Language.PORTUGUESE: LanguageCode.PT,
        }

    def detect(self, text: str) -> LanguageDetectionResult:
        if not text or len(text.strip()) < 5:
            return LanguageDetectionResult(LanguageCode.UNKNOWN, 0.0, None, 0.0, 0.0, len(text.strip()) if text else 0)
            
        confidences = self.detector.compute_language_confidence_values(text)
        
        if not confidences:
            return LanguageDetectionResult(LanguageCode.UNKNOWN, 0.0, None, 0.0, 0.0, len(text.strip()))
            
        top_lang = self._lang_map.get(confidences[0].language, LanguageCode.UNKNOWN)
        top_conf = confidences[0].value
        
        runner_up_lang = None
        runner_up_conf = 0.0
        margin = top_conf
        
        if len(confidences) > 1:
            runner_up_lang = self._lang_map.get(confidences[1].language, LanguageCode.UNKNOWN)
            runner_up_conf = confidences[1].value
            margin = top_conf - runner_up_conf
            
        return LanguageDetectionResult(
            language=top_lang,
            confidence=top_conf,
            runner_up_language=runner_up_lang,
            runner_up_confidence=runner_up_conf,
            margin=margin,
            analyzable_characters=len(text.strip())
        )

# Singleton instance initialized at startup
language_detector = LanguageDetectorPort()
