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

    _PROSE_FIELDS = frozenset({
        "title", "headline", "hook", "body", "cta", "supporting_copy", "footer",
        "bullets", "label", "value_or_copy", "relationship", "alt_text_draft",
        "statement", "key_points", "uncertainties", "safety_notes", "forbidden_claims",
        "recommended_angle", "notes", "message", "topic", "angle", "rationale",
        "target_effect", "planning_rationale", "description", "prompt", "image_prompt",
    })
    _SOURCE_FIELDS = frozenset({"evidence", "sources", "provenance", "evidence_bundle"})

    @classmethod
    def _collect_json_prose(cls, value, prose_field: bool = False) -> list[str]:
        if isinstance(value, str):
            return [cls._strip_technical_content(value)] if prose_field and cls._is_human_prose_value(value) else []
        if isinstance(value, dict):
            return [text for key, nested in value.items() if key not in cls._SOURCE_FIELDS
                    for text in cls._collect_json_prose(nested, key in cls._PROSE_FIELDS)]
        if isinstance(value, list):
            return [text for nested in value for text in cls._collect_json_prose(nested, prose_field)]
        return []

    @classmethod
    def _extract_structured_prose(cls, text: str) -> str | None:
        try:
            value = text.strip()
            if value.startswith("```") and value.endswith("```"):
                value = value[value.find("\n") + 1:-3].strip()
            parsed = json.loads(value)
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
            structured = LanguageValidator._extract_structured_prose(text)
            return structured if structured is not None else LanguageValidator._strip_technical_content(text)

        return text

    @staticmethod
    def validate(text: str, expected_code: LanguageCode, artifact_type: ArtifactType) -> LanguageValidationResult:
        if expected_code == LanguageCode.AUTO or expected_code == LanguageCode.UNKNOWN:
            return LanguageValidationResult(expected_code, LanguageCode.UNKNOWN, ValidationStatus.INDETERMINATE, "Auto or unknown expected language", 0.0)

        prose = LanguageValidator._extract_prose(text, artifact_type)
        detect_result = language_detector.detect(prose)

        LANGUAGE_MIN_CONFIDENCE = float(os.environ.get("LANGUAGE_MIN_CONFIDENCE", "0.6"))
        LANGUAGE_MIN_MARGIN = float(os.environ.get("LANGUAGE_MIN_MARGIN", "0.2"))

        # A long wrong-language field cannot hide behind a larger correct body.
        # Short API/product phrases do not have enough signal for this field gate.
        structured_prose = LanguageValidator._extract_structured_prose(text)
        if structured_prose is not None:
            for field_prose in structured_prose.splitlines():
                if len(field_prose) < 80 or len(field_prose.split()) < 12:
                    continue
                field_result = language_detector.detect(field_prose)
                if (field_result.language not in {LanguageCode.UNKNOWN, expected_code}
                        and field_result.confidence >= LANGUAGE_MIN_CONFIDENCE
                        and field_result.margin >= LANGUAGE_MIN_MARGIN):
                    return LanguageValidationResult(expected_code, field_result.language,
                        ValidationStatus.MISMATCH, "A human-facing field violates the target language", field_result.confidence)

        detected = detect_result.language
        conf = detect_result.confidence

        if detected == LanguageCode.UNKNOWN or conf < LANGUAGE_MIN_CONFIDENCE or detect_result.margin < LANGUAGE_MIN_MARGIN:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.INDETERMINATE, "Could not determine language confidently", conf)

        if detected == expected_code:
            return LanguageValidationResult(expected_code, detected, ValidationStatus.MATCH, "Language matches exactly", conf)

        return LanguageValidationResult(expected_code, detected, ValidationStatus.MISMATCH, f"Expected {expected_code.value} but got {detected.value}", conf)
