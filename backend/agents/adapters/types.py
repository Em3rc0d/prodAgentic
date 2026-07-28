from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any, AsyncGenerator

class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION = "AUTHENTICATION"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    PROVIDER_PROTOCOL_ERROR = "PROVIDER_PROTOCOL_ERROR"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

@dataclass
class ModelExecutionResult:
    actual_model: str
    content: str
    raw_response: Optional[Any] = None

class ModelExecutionError(Exception):
    def __init__(self, code: ErrorCode, message: str, retryable: bool, fallback_allowed: bool, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.fallback_allowed = fallback_allowed
        self.original_exception = original_exception

    def __str__(self):
        return f"[{self.code.value}] {self.message}"

class ProviderAdapter:
    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        raise NotImplementedError
    
    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        # Should yield ("chunk", text) or other tuples
        raise NotImplementedError
        yield
