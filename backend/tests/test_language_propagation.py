import pytest
from core.context import GenerationContext, LanguageCode
from core.language import language_detector

def test_explicit_target_wins():
    ctx = GenerationContext(
        run_id="run-1",
        topic="Hello world",
        style="listicle",
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.EN,
        source_detection_confidence=1.0,
        requested_target_language=LanguageCode.ES,
        resolved_target_language=LanguageCode.ES,
        image_prompt_language=LanguageCode.EN
    )
    assert ctx.resolved_target_language == LanguageCode.ES

def test_auto_resolves_before_ideas():
    detected = language_detector.detect("Este es un topic en español y quiero ideas")
    assert detected == LanguageCode.ES

def test_low_confidence_uses_configured_default():
    detected = language_detector.detect("a")
    assert detected == LanguageCode.UNKNOWN
