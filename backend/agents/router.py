import asyncio
import uuid
from typing import AsyncGenerator, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from core.model_registry import ModelProfile, get_models_for_profile
from .adapters.types import ModelExecutionError, ErrorCode, ProviderAdapter
from core.validator import LanguageValidator, ValidationStatus, ArtifactType
from core.context import GenerationContext, LanguageCode

@dataclass
class AttemptStarted:
    model_id: str
    attempt_id: str
    provider: str

@dataclass
class ContentChunk:
    text: str
    attempt_id: str

@dataclass
class AttemptFailed:
    reason: str
    attempt_id: str

@dataclass
class AttemptResetRequired:
    reason: str
    attempt_id: str

@dataclass
class AttemptCompleted:
    attempt_id: str

@dataclass
class RoutingExhausted:
    reason: str

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

@dataclass
class CircuitBreaker:
    state: CircuitState = CircuitState.CLOSED
    opened_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    failure_count: int = 0
    last_failure_category: Optional[str] = None
    _half_open_probe_active: bool = False
    
    def record_failure(self, category: str, ttl_seconds: int = 60):
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now(timezone.utc)
        self.expires_at = self.opened_at + timedelta(seconds=ttl_seconds)
        self.failure_count += 1
        self.last_failure_category = category
        self._half_open_probe_active = False
        
    def is_allowed(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if datetime.now(timezone.utc) > self.expires_at:
                self.state = CircuitState.HALF_OPEN
                self._half_open_probe_active = True
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            if not getattr(self, '_half_open_probe_active', False):
                self._half_open_probe_active = True
                return True
            return False
            
    def record_success(self):
        self.state = CircuitState.CLOSED
        self.opened_at = None
        self.expires_at = None
        self.failure_count = 0
        self.last_failure_category = None
        self._half_open_probe_active = False

@dataclass
class RoutingPolicy:
    max_transport_retries_per_route: int = 1
    max_language_repairs_per_stage: int = 1
    max_models_per_stage: int = 2
    max_total_attempts: int = 5
    allow_direct_provider_fallback_after_n8n_failure: bool = False

@dataclass
class ModelExecutionRequest:
    context: GenerationContext
    model_profile: ModelProfile
    artifact_type: ArtifactType
    system_instruction: str
    user_prompt: str
    expected_output_language: LanguageCode

class ModelRouter:
    def __init__(self, google_adapter: ProviderAdapter, n8n_adapter: ProviderAdapter = None, routing_policy: RoutingPolicy = None):
        self.google_adapter = google_adapter
        self.n8n_adapter = n8n_adapter
        self.policy = routing_policy or RoutingPolicy()
        self._provider_breakers: dict[str, CircuitBreaker] = {}
        self._model_breakers: dict[str, CircuitBreaker] = {}

    def _get_provider_breaker(self, provider: str) -> CircuitBreaker:
        if provider not in self._provider_breakers:
            self._provider_breakers[provider] = CircuitBreaker()
        return self._provider_breakers[provider]

    def _get_model_breaker(self, provider: str, model: str) -> CircuitBreaker:
        key = f"{provider}::{model}"
        if key not in self._model_breakers:
            self._model_breakers[key] = CircuitBreaker()
        return self._model_breakers[key]
        
    def _record_success(self, provider: str, model: str):
        self._get_provider_breaker(provider).record_success()
        self._get_model_breaker(provider, model).record_success()

    def _get_adapters(self) -> list[tuple[str, ProviderAdapter]]:
        adapters = []
        if self.n8n_adapter:
            adapters.append(("n8n", self.n8n_adapter))
        if self.google_adapter:
            adapters.append(("google", self.google_adapter))
        return adapters

    async def stream_generation(self, request: ModelExecutionRequest) -> AsyncGenerator[RouterEvent, None]:
        if not self._get_adapters():
            yield RoutingExhausted("No viable provider adapters available.")
            return

        models = get_models_for_profile(request.model_profile)
        total_attempts = 0
        models_tried = 0
        
        for model_def in models:
            if models_tried >= self.policy.max_models_per_stage:
                break
                
            models_tried += 1
            
            for provider_name, adapter in self._get_adapters():
                if not self._get_provider_breaker(provider_name).is_allowed():
                    if provider_name == "n8n" and not self.policy.allow_direct_provider_fallback_after_n8n_failure:
                        yield RoutingExhausted("n8n provider circuit is open and bypass is disabled")
                        return
                    continue
                    
                if not self._get_model_breaker(provider_name, model_def.model_id).is_allowed():
                    continue
                
                transport_retries = 0
                language_repairs = 0
                current_system_instruction = request.system_instruction
                
                while transport_retries <= self.policy.max_transport_retries_per_route and total_attempts < self.policy.max_total_attempts:
                    total_attempts += 1
                    attempt_id = str(uuid.uuid4())
                    successful_start = False
                    accumulated_text = ""
                    
                    try:
                        stream_gen = adapter.stream(
                            model=model_def.model_id,
                            prompt=request.user_prompt,
                            system_instruction=current_system_instruction,
                            attempt_id=attempt_id,
                            run_id=request.context.run_id,
                            profile_name=request.model_profile.value
                        )
                        
                        yield AttemptStarted(model_def.model_id, attempt_id, provider_name)
                        
                        async for chunk_type, chunk_text in stream_gen:
                            successful_start = True
                            accumulated_text += chunk_text
                            yield ContentChunk(chunk_text, attempt_id)
                        
                        # Validate the language
                        validation_result = LanguageValidator.validate(accumulated_text, request.expected_output_language, request.artifact_type)
                        
                        if validation_result.status == ValidationStatus.MISMATCH:
                            error_msg = f"LANGUAGE_MISMATCH: {validation_result.reason}"
                            yield AttemptFailed(error_msg, attempt_id)
                            yield AttemptResetRequired(error_msg, attempt_id)
                            
                            if language_repairs < self.policy.max_language_repairs_per_stage:
                                language_repairs += 1
                                # Instruction for semantic retry
                                repair_instruction = f"\n\nThe previous response violated the language contract.\nRewrite the complete response in {request.expected_output_language.value}.\nDo not summarize it.\nDo not add or remove facts.\nPreserve code, API names, identifiers and product names."
                                current_system_instruction += repair_instruction
                                continue # retry same provider/model with repaired prompt
                            else:
                                # Open circuit for this model because semantic repairs failed
                                self._get_model_breaker(provider_name, model_def.model_id).record_failure("LANGUAGE_MISMATCH")
                                break # break while loop to move to next provider/model

                        self._record_success(provider_name, model_def.model_id)
                        yield AttemptCompleted(attempt_id)
                        return # fully successful
                        
                    except ModelExecutionError as exec_error:
                        if successful_start:
                            yield AttemptFailed(exec_error.sanitized_message, attempt_id)
                            yield AttemptResetRequired(exec_error.sanitized_message, attempt_id)
                        else:
                            yield AttemptFailed(exec_error.sanitized_message, attempt_id)

                        if exec_error.category in (
                            ErrorCode.INVALID_REQUEST, 
                            ErrorCode.AUTHENTICATION, 
                            ErrorCode.CANCELLED,
                            ErrorCode.QUOTA_EXHAUSTED,
                            ErrorCode.UNKNOWN
                        ):
                            yield RoutingExhausted(f"Terminal error: {exec_error.category.value}")
                            return
                            
                        if exec_error.category == ErrorCode.MODEL_NOT_FOUND:
                            self._get_model_breaker(provider_name, model_def.model_id).record_failure(exec_error.category.value)
                            break # Move to next provider/model
                        
                        # Provider endpoint failures -> transport retries
                        if exec_error.category in (ErrorCode.TIMEOUT, ErrorCode.SERVICE_UNAVAILABLE, ErrorCode.PROVIDER_PROTOCOL_ERROR, ErrorCode.RATE_LIMITED, ErrorCode.MODEL_MISMATCH):
                            if exec_error.retryable and transport_retries < self.policy.max_transport_retries_per_route:
                                transport_retries += 1
                                await asyncio.sleep(2 ** transport_retries)
                                continue # retry same provider/model
                                
                            self._get_model_breaker(provider_name, model_def.model_id).record_failure(exec_error.category.value)
                            
                            if provider_name == "n8n":
                                self._get_provider_breaker(provider_name).record_failure(exec_error.category.value)
                                if not self.policy.allow_direct_provider_fallback_after_n8n_failure:
                                    yield RoutingExhausted("n8n provider failed and bypass is disabled")
                                    return
                            
                            break # Move to next provider
                            
                        # Catch-all unhandled categories -> terminal conservative
                        yield RoutingExhausted(f"Terminal error: {exec_error.category.value}")
                        return
                            
        yield RoutingExhausted("All eligible models and providers exhausted or failed.")
