import pytest
from core.validator import LanguageValidator, ValidationStatus, ArtifactType
from core.context import LanguageCode

def test_detector_is_reused_not_recreated_per_request():
    from core.language import language_detector
    assert language_detector is not None

def test_spanish_technical_post_is_match():
    text = "Este post explica cómo usar Kafka con Spring Boot y evitar el error TimeoutException."
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.MATCH

def test_portuguese_text_is_not_spanish():
    text = "Este post explica como usar o Kafka para evitar erros em produção."
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.MISMATCH

def test_json_ideas_validate_only_string_values():
    text = '["Primera idea excelente", "Segunda idea sobre microservicios", "Tercera idea sobre bases de datos"]'
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.IDEAS)
    assert result.status == ValidationStatus.MATCH

def test_urls_and_code_are_excluded():
    text = "Here is some code ```python print('Hola mundo')``` and a url https://es.wikipedia.org"
    result = LanguageValidator.validate(text, LanguageCode.EN, ArtifactType.RESEARCH)
    # the code and url should be stripped, leaving "Here is some code and a url"
    assert result.status == ValidationStatus.MATCH

def test_detector_failure_returns_indeterminate():
    text = "123 456 789"
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.INDETERMINATE
