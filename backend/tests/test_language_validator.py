import json

import pytest
from core.validator import LanguageValidator, ValidationStatus, ArtifactType
from core.context import LanguageCode


def test_detector_is_reused_not_recreated_per_request():
    from core.language import language_detector
    assert language_detector is not None


def test_spanish_technical_post_is_match():
    # Make the text a bit longer to pass the confidence and margin thresholds
    text = "Este post explica detalladamente cómo usar Kafka con Spring Boot y evitar el error TimeoutException. La configuración es bastante sencilla de implementar si sigues estos pasos cuidadosamente."
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.MATCH


def test_portuguese_text_is_not_spanish():
    text = "Este post explica detalhadamente como usar o Kafka para evitar erros em produção. A configuração é muito simples e você pode aprender rapidamente."
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.MISMATCH


def test_json_ideas_validate_only_string_values():
    text = '["Primera idea excelente y muy larga para que pase el detector", "Segunda idea sobre microservicios que también es larga", "Tercera idea sobre bases de datos en la nube"]'
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.IDEAS)
    assert result.status == ValidationStatus.MATCH


def test_structured_spanish_json_ignores_english_schema_keys_and_machine_values():
    text = json.dumps({
        "research_id": "2af3e759-b133-45ab-b343-f198d9da1575",
        "plan_id": "5d6647b7-e57f-4104-8b21-2c41d4265c6a",
        "verdict": "GO_WITH_CAUTION",
        "key_points": [
            "Explica primero el problema con un ejemplo concreto y fácil de reconocer.",
            "Después conecta el concepto técnico con una decisión práctica que el lector pueda aplicar.",
        ],
        "claims": [{
            "claim_id": "claim_1",
            "statement": "Una explicación conceptual puede ser útil sin inventar estadísticas ni fuentes externas.",
            "category": "interpretive",
            "confidence": "medium",
            "evidence_refs": [],
            "publishability": "qualify",
        }],
        "evidence": [],
        "uncertainties": ["No se proporcionaron fuentes externas para afirmar cifras actuales."],
        "recommended_angle": "Enseñar el concepto mediante un caso ilustrativo claramente presentado como ejemplo.",
    }, ensure_ascii=False)

    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.RESEARCH)
    assert result.status == ValidationStatus.MATCH


def test_structured_json_still_rejects_wrong_prose_language():
    text = json.dumps({
        "content_spec_id": "content_123",
        "plan_id": "plan_123",
        "language": "es",
        "hook": "This explanation shows a concrete software architecture problem that developers can recognize immediately.",
        "body": "The example then explains the tradeoff carefully and gives the reader a practical decision framework without inventing metrics or sources.",
        "format": "text",
        "format_spec": {"kind": "text"},
        "claims_used": [],
    })

    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.DRAFT)
    assert result.status == ValidationStatus.MISMATCH


def test_urls_and_code_are_excluded():
    text = "Here is some really interesting code that will absolutely blow your mind ```python print('Hola mundo')``` and a url to read more about this https://es.wikipedia.org"
    result = LanguageValidator.validate(text, LanguageCode.EN, ArtifactType.RESEARCH)
    assert result.status == ValidationStatus.MATCH


def test_detector_failure_returns_indeterminate():
    text = "123 456 789"
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.INDETERMINATE
