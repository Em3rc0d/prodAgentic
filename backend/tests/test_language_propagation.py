import pytest
import os
from core.context import GenerationContext, LanguageCode
from core.language import language_detector

def test_source_language_is_detected_with_explicit_target():
    from agents.orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator(None)
    ctx = orchestrator._resolve_context("Este es un texto en español para probar", "listicle", "en", "en")
    assert ctx.detected_source_language == LanguageCode.ES
    assert ctx.resolved_target_language == LanguageCode.EN
    assert ctx.requested_target_language == LanguageCode.EN

def test_auto_uses_configured_default_when_indeterminate(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "en")
    from agents.orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator(None)
    ctx = orchestrator._resolve_context("a", "listicle", "auto", "en")
    assert ctx.detected_source_language == LanguageCode.UNKNOWN
    assert ctx.resolved_target_language == LanguageCode.EN

def test_invalid_default_language_fails_readiness(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "invalid_lang")
    from core.container import ApplicationContainer
    container = ApplicationContainer()
    container.startup()
    assert container.config_error is not None
    assert "Invalid APP_DEFAULT_LANGUAGE" in container.config_error
