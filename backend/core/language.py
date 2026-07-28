from lingua import LanguageDetectorBuilder, Language
from core.context import LanguageCode

class LanguageDetectorPort:
    def __init__(self):
        # We restrict the detector to the languages our application supports
        # to prevent absurd false positives on technical text
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

    def detect(self, text: str) -> LanguageCode:
        # If text is too short or empty, Lingua might return None or unpredictable results
        if not text or len(text.strip()) < 5:
            return LanguageCode.UNKNOWN
            
        result = self.detector.detect_language_of(text)
        
        if result == Language.SPANISH:
            return LanguageCode.ES
        elif result == Language.ENGLISH:
            return LanguageCode.EN
        elif result == Language.PORTUGUESE:
            return LanguageCode.PT
        
        return LanguageCode.UNKNOWN

# Singleton instance initialized at startup
language_detector = LanguageDetectorPort()
