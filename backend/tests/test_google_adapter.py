import pytest
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.types import ErrorCode, ModelExecutionError
from google.genai.errors import APIError
from unittest.mock import MagicMock

class MockAPIError(APIError):
    def __init__(self, message, code):
        Exception.__init__(self, message)
        self.code = code

def test_google_adapter_error_translation():
    adapter = GoogleDirectAdapter(MagicMock())
    
    # 429
    err = MockAPIError("quota exceeded", 429)
    translated = adapter._translate_error(err)
    assert translated.code == ErrorCode.QUOTA_EXHAUSTED
    assert translated.retryable is False
    
    err2 = MockAPIError("rate limit", 429)
    err2.message = "rate limit" # to trigger rate limit check
    translated2 = adapter._translate_error(err2)
    assert translated2.code == ErrorCode.RATE_LIMITED
    assert translated2.retryable is True

    # 404
    err3 = MockAPIError("model not found", 404)
    translated3 = adapter._translate_error(err3)
    assert translated3.code == ErrorCode.MODEL_NOT_FOUND
    assert translated3.fallback_allowed is True
