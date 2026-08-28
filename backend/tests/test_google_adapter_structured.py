from types import SimpleNamespace

import pytest

import agents.adapters.google_adapter as google_module
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.types import ErrorCode


class FakeApiError(Exception):
    def __init__(self, code, message, status="INVALID_ARGUMENT"):
        super().__init__(message)
        self.code = code
        self.status = status


def adapter():
    return GoogleDirectAdapter(SimpleNamespace(aio=SimpleNamespace()))


def test_structured_schema_unsupported_is_safe_model_fallback(monkeypatch):
    monkeypatch.setattr(google_module, "APIError", FakeApiError)
    error = FakeApiError(
        400,
        "response_schema is not supported for this model",
    )

    translated = adapter()._translate_error(
        error,
        "model-primary",
        "attempt-1",
        structured_output=True,
    )

    assert translated.category == ErrorCode.MODEL_CAPABILITY_UNAVAILABLE
    assert translated.fallback_allowed is True
    assert translated.retryable is False
    assert translated.sanitized_message == "Google API Error: MODEL_CAPABILITY_UNAVAILABLE"


def test_same_400_without_structured_context_remains_terminal_invalid_request(monkeypatch):
    monkeypatch.setattr(google_module, "APIError", FakeApiError)
    error = FakeApiError(
        400,
        "response_schema is not supported for this model",
    )

    translated = adapter()._translate_error(
        error,
        "model-primary",
        "attempt-1",
        structured_output=False,
    )

    assert translated.category == ErrorCode.INVALID_REQUEST
    assert translated.fallback_allowed is False


def test_unrelated_structured_400_does_not_get_reclassified(monkeypatch):
    monkeypatch.setattr(google_module, "APIError", FakeApiError)
    error = FakeApiError(400, "invalid contents payload")

    translated = adapter()._translate_error(
        error,
        "model-primary",
        "attempt-1",
        structured_output=True,
    )

    assert translated.category == ErrorCode.INVALID_REQUEST
    assert translated.fallback_allowed is False


@pytest.mark.asyncio
async def test_generate_rejects_two_competing_schema_authorities():
    with pytest.raises(ValueError, match="mutually exclusive"):
        await adapter().generate(
            model="model-primary",
            prompt="test",
            response_schema=dict,
            response_json_schema={"type": "object"},
        )
