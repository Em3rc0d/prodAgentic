import json
import re
import os
from enum import Enum
from dataclasses import dataclass
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
    confidence: float = 0.0


class LanguageValidator:
    _UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.IGNORECASE)
    _HEX = re.compile(r"^[0-9a-f]{32,}$", re.IGNORECASE)
    _MACHINE_TOKEN = re.compile(r"^[A-Z0-9_:.\-/]{2,80}$")
    _SNAKE_TOKEN = re.compile(r"^[a-z][a-z0-9_\-]{1,80}$")

    @staticmethod
    def _strip_technical_content(text: str) -> str:
        # Strip code blocks
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        # Strip inline code
        text = re.sub(r"`.*?`", " ", text)
        # Strip URLs
        text = re.sub(r"https?://\S+", " ", text)
        return text.strip()

    @classmethod
    def _is_human_prose_value(cls, value: str) -> bool:
        candidate = cls._strip_technical_content(value).strip()
        if len(candidate) < 3:
            return False
        if cls._UUID.fullmatch(candidate) or cls._HEX.fullmatch(candidate):
            return False
        if cls._MACHINE_TOKEN.fullmatch(candidate):
            return False
        # JSON contracts contain many identifiers/enums such as factual,
        # allowed, single_image and content_spec_id-like values. A lone machine
        # token is not useful evidence for natural-language classification.
        if " " not in candidate and cls._SNAKE_TOKEN.fullmatch(candidate):
            return False
        return True

    @classmethod
    def _collect_json_prose(cls, value) -> list[str]:
        prose: list[str] = []
        if isinstance(value, str):
            if cls._is_human_prose_value(value):
                cleaned = cls._strip_technical_content(value)
                if cleaned:
                    prose.append(cleaned)
            return prose
        if isinstance(value, dict):
            # Deliberately ignore object keys: structured contracts use English
            # schema names regardless of the target language.
            for nested in value.values():
                prose.extend(cls._collect_json_prose(nested))
            return prose
        if isinstance(value, list):
            for nested in value:
                prose.extend(cls._collect_json_prose(nested))
        return prose

    @classmethod
    def _extract_structured_prose(cls, text: str) -> str | None:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        values = cls._collect_json_prose(parsed)
        return "\n".join(values)

    @staticmethod
    def _extract_prose(text: str, artifact_type: ArtifactType) -> str:
        if artifact_type == ArtifactType.IDEAS:
            try:
                ideas = json.loads(text)
                if isinstance(ideas, list) and all(isinstance(i, str) for i in ideas):
                    return "\n".join(ideas)
            except json.JSONDecodeError:
                pass
            return LanguageValidator._strip_technical_content(text)

        if artifact_type in {ArtifactType.RESEARCH, ArtifactType.DRAFT, ArtifactType.FINAL}:
            structured = LanguageValidator._extract_structured_prose(text)
            if structured is not None:
                return structured
            return LanguageValidator._strip_technical_content(text)

        if artifact_type == ArtifactType.VISUAL:
            return text.strip()

        return text

    @staticmethod
    def validate(text: str, expected_code: LanguageCode, artifact_type: ArtifactType) -> LanguageValidationResult:
        if expected_code == LanguageCode.AUTO or expected_code == LanguageCode.UNKNOWN:
            return LanguageValidationResult(expected_code, LanguageCode.UNKNOWN, ValidationStatus.INDETERMINATE, "Auto or unknown expected language", 0.0)

        prose = LanguageValidator._extract_prose(text, artifact_type)
        detect_result = language_detector.detect(prose)

        LANGUAGE_MIN_CONFIDENCE = float(os.environ.get("LANGUAGE_MIN_CONFIDENCE", "0.6"))
        LANGUAGE_MIN_MARGIN = float(os.environ.get("LANGUAGE_MIN_MARGIN", "0.2"))

        detected = detect_result.language
        conf = detect_result.confidence

        if detected == LanguageCode.UNKNOWN or conf < LANGUAGE_MIN_CONFIDENCE or detect_result.margin < LANGUAGE_MIN_MARGIN:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.INDETERMINATE, "Could not determine language confidently", conf)

        if detected == expected_code:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.MATCH, "Language matches exactly", conf)

        return LanguageValidationResult(expected_code, detected, ValidationStatus.MISMATCH, f"Expected {expected_code.value} but got {detected.value}", conf)
