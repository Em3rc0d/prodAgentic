import json
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from core.context import LanguageCode
from core.language import language_detector

class ValidationStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INDETERMINATE = "INDETERMINATE"

class ArtifactType(str, Enum):
    IDEAS = "IDEAS"
    RESEARCH = "RESEARCH"
    DRAFT = "DRAFT"
    FINAL = "FINAL"
    VISUAL = "VISUAL"

@dataclass
class LanguageValidationResult:
    expected_language: LanguageCode
    detected_language: LanguageCode
    status: ValidationStatus
    reason: str

class LanguageValidator:
    @staticmethod
    def _strip_technical_content(text: str) -> str:
        # Strip code blocks
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        # Strip inline code
        text = re.sub(r"`.*?`", " ", text)
        # Strip URLs
        text = re.sub(r"https?://\S+", " ", text)
        return text.strip()

    @staticmethod
    def _extract_prose(text: str, artifact_type: ArtifactType) -> str:
        if artifact_type == ArtifactType.IDEAS:
            try:
                ideas = json.loads(text)
                if isinstance(ideas, list):
                    # Join string values if it's an array of strings
                    # Or if it's an array of objects, try to extract values
                    if all(isinstance(i, str) for i in ideas):
                        return "\n".join(ideas)
            except json.JSONDecodeError:
                pass
            # Fallback if not pure JSON array
            return LanguageValidator._strip_technical_content(text)
            
        elif artifact_type == ArtifactType.RESEARCH:
            return LanguageValidator._strip_technical_content(text)
            
        elif artifact_type == ArtifactType.DRAFT:
            return LanguageValidator._strip_technical_content(text)
            
        elif artifact_type == ArtifactType.FINAL:
            return LanguageValidator._strip_technical_content(text)
            
        elif artifact_type == ArtifactType.VISUAL:
            return text.strip()
            
        return text

    @staticmethod
    def validate(text: str, expected_code: LanguageCode, artifact_type: ArtifactType) -> LanguageValidationResult:
        if expected_code == LanguageCode.AUTO or expected_code == LanguageCode.UNKNOWN:
            return LanguageValidationResult(expected_code, LanguageCode.UNKNOWN, ValidationStatus.INDETERMINATE, "Auto or unknown expected language")
            
        prose = LanguageValidator._extract_prose(text, artifact_type)
        detected = language_detector.detect(prose)
        
        if detected == LanguageCode.UNKNOWN:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.INDETERMINATE, "Could not determine language confidently")
            
        if detected == expected_code:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.MATCH, "Language matches exactly")
        else:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.MISMATCH, f"Expected {expected_code.value} but got {detected.value}")
