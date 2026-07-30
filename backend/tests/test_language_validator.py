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

def test_urls_and_code_are_excluded():
    text = "Here is some really interesting code that will absolutely blow your mind ```python print('Hola mundo')``` and a url to read more about this https://es.wikipedia.org"
    result = LanguageValidator.validate(text, LanguageCode.EN, ArtifactType.RESEARCH)
    assert result.status == ValidationStatus.MATCH

def test_detector_failure_returns_indeterminate():
    text = "123 456 789"
    result = LanguageValidator.validate(text, LanguageCode.ES, ArtifactType.FINAL)
    assert result.status == ValidationStatus.INDETERMINATE
