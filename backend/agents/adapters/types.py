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
    provider: str
    requested_model: str
    actual_model: str
    model_profile: str
    attempt_id: str
    content: str
    finish_reason: str = "UNKNOWN"
    usage: Optional[dict] = None
    latency_ms: Optional[int] = None
    provider_request_id: Optional[str] = None
    warnings: Optional[list] = None
    raw_response: Optional[Any] = None

class ModelExecutionError(Exception):
    def __init__(
        self, 
        category: ErrorCode, 
        provider: str,
        model_id: str,
        attempt_id: str,
        http_status: Optional[int],
        provider_error_code: Optional[str],
        retryable: bool, 
        fallback_allowed: bool, 
        sanitized_message: str,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(sanitized_message)
        self.category = category
        self.provider = provider
        self.model_id = model_id
        self.attempt_id = attempt_id
        self.http_status = http_status
        self.provider_error_code = provider_error_code
        self.retryable = retryable
        self.fallback_allowed = fallback_allowed
        self.sanitized_message = sanitized_message
        self.original_exception = original_exception

    def __str__(self):
        return f"[{self.category.value}] {self.sanitized_message} (Provider: {self.provider}, Model: {self.model_id})"

class ProviderAdapter:
    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        raise NotImplementedError
    
    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        # Should yield ("chunk", text) or other tuples
        raise NotImplementedError
        yield
