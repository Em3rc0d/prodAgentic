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
from core.execution_budget import stage_deadline as bounded_deadline

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
    # Internal typed lineage; reason remains compatible with existing consumers.
    failure_code: str | None = None

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
    failure_code: str = "ROUTING_EXHAUSTED"

@dataclass
class ValidationWarning:
    code: str
    expected_language: str
    detected_language: str
    confidence: float
    artifact_type: str
    attempt_id: str
    reason: str

RouterEvent = (
    AttemptStarted
    | ContentChunk
    | AttemptFailed
    | AttemptResetRequired
    | AttemptCompleted
    | RoutingExhausted
    | ValidationWarning
)
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
    # Hard wall-clock budget for one governed model-routing stage. This must stay
    # below the browser/API request budget so a hung provider fails closed instead
    # of leaving the UI waiting after its request has already been aborted.
    max_stage_seconds: float = 75.0
    per_attempt_seconds: float = 25.0
    minimum_fallback_seconds: float = 10.0


@dataclass
class RoutingBudget:
    deadline: float
    attempts: int = 0
    language_repairs: int = 0


def allocate_route_seconds(remaining: float, eligible_routes: int, policy: RoutingPolicy) -> float:
    """Reserve time for every remaining route; repairs consume this route's slice."""
    if remaining <= 0 or eligible_routes <= 0:
        return 0.0
    fair_share = remaining / eligible_routes
    reserve = min(policy.minimum_fallback_seconds, fair_share) * (eligible_routes - 1)
    return max(0.0, min(remaining - reserve, max(fair_share, policy.per_attempt_seconds)))

@dataclass
class ModelExecutionRequest:
    context: GenerationContext
    model_profile: ModelProfile
    artifact_type: ArtifactType
    system_instruction: str
    user_prompt: str
    expected_output_language: LanguageCode
    budget: RoutingBudget | None = None
    response_mime_type: str | None = None
    response_json_schema: dict[str, Any] | None = None

class ModelRouter:
    def __init__(self, google_adapter: ProviderAdapter, n8n_adapter: ProviderAdapter = None, routing_policy: RoutingPolicy = None):
        self.google_adapter = google_adapter
        self.n8n_adapter = n8n_adapter
        self.policy = routing_policy or RoutingPolicy()
        self._provider_breakers: dict[str, CircuitBreaker] = {}
        self._model_breakers: dict[str, CircuitBreaker] = {}

    def isolated(self) -> "ModelRouter":
        """Reuse configuration/adapters without inheriting another request's breakers."""
        return ModelRouter(
            google_adapter=self.google_adapter,
            n8n_adapter=self.n8n_adapter,
            routing_policy=self.policy,
        )

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
        loop = asyncio.get_running_loop()
        budget = request.budget or RoutingBudget(bounded_deadline(self.policy.max_stage_seconds))
        adapters = self._get_adapters()
        # An n8n installation cannot silently escape to direct Google.
        if self.n8n_adapter and not self.policy.allow_direct_provider_fallback_after_n8n_failure:
            adapters = [(name, adapter) for name, adapter in adapters if name == "n8n"]
        models = get_models_for_profile(request.model_profile)[:self.policy.max_models_per_stage]
        if not adapters or not models:
            yield RoutingExhausted("No viable provider route is available.", "NO_VIABLE_PROVIDER")
            return
        routes = [(model.model_id, name, adapter) for model in models for name, adapter in adapters]
        last_code = "ROUTING_EXHAUSTED"
        for index, (model, provider, adapter) in enumerate(routes):
            if budget.attempts >= self.policy.max_total_attempts:
                break
            if loop.time() >= budget.deadline:
                yield RoutingExhausted("Model stage deadline exceeded.", "STAGE_TIMEOUT")
                return
            if not self._get_provider_breaker(provider).is_allowed():
                continue
            if not self._get_model_breaker(provider, model).is_allowed():
                continue
            remaining_routes = 1 + sum(
                self._get_provider_breaker(name).state != CircuitState.OPEN
                and self._get_model_breaker(name, other_model).state != CircuitState.OPEN
                for other_model, name, _ in routes[index + 1:]
            )
            remaining_routes = min(remaining_routes, self.policy.max_total_attempts - budget.attempts)
            route_deadline = loop.time() + allocate_route_seconds(
                budget.deadline - loop.time(), remaining_routes, self.policy,
            )
            transport_retries = 0
            instruction = request.system_instruction
            while budget.attempts < self.policy.max_total_attempts:
                now = loop.time()
                stage_remaining = budget.deadline - now
                route_remaining = route_deadline - now
                seconds = min(self.policy.per_attempt_seconds, route_remaining, stage_remaining)
                if seconds <= 0:
                    break
                # If this timer is the global wall-clock limit, classify it as a
                # stage timeout. Otherwise it is a route timeout and fallback must
                # still be allowed to consume its reserved capacity.
                stage_limited_timeout = stage_remaining <= route_remaining + 1e-6 and stage_remaining <= self.policy.per_attempt_seconds + 1e-6
                budget.attempts += 1
                attempt_id = str(uuid.uuid4())
                text = ""
                stream = None
                yield AttemptStarted(model, attempt_id, provider)
                try:
                    stream = adapter.stream(
                        model=model, prompt=request.user_prompt, system_instruction=instruction,
                        attempt_id=attempt_id, run_id=request.context.run_id,
                        profile_name=request.model_profile.value,
                        response_mime_type=request.response_mime_type,
                        response_json_schema=request.response_json_schema,
                    )
                    async with asyncio.timeout(seconds):
                        async for _, chunk in stream:
                            if not isinstance(chunk, str) or len(text) + len(chunk) > 1_000_000:
                                raise ValueError("Provider text exceeds the bounded artifact envelope")
                            text += chunk
                            yield ContentChunk(chunk, attempt_id)
                    result = LanguageValidator.validate(text, request.expected_output_language, request.artifact_type)
                    if result.status == ValidationStatus.INDETERMINATE:
                        yield ValidationWarning("LANGUAGE_INDETERMINATE", result.expected_language.value,
                                                result.detected_language.value, result.confidence,
                                                request.artifact_type.value, attempt_id, result.reason)
                    if result.status == ValidationStatus.MISMATCH:
                        last_code = "LANGUAGE_MISMATCH"
                        yield AttemptFailed("Language contract mismatch.", attempt_id, last_code)
                        yield AttemptResetRequired("Language contract mismatch.", attempt_id)
                        # Retain an attempt as well as time for each next route.
                        can_repair = budget.attempts < self.policy.max_total_attempts - (remaining_routes - 1)
                        if (can_repair and budget.language_repairs < self.policy.max_language_repairs_per_stage
                                and route_deadline - loop.time() > 0.05):
                            budget.language_repairs += 1
                            instruction += (
                                "\nThe previous response violated the language contract. "
                                f"Rewrite human-facing prose in {request.expected_output_language.value}. "
                                "Preserve JSON keys, enums, IDs, source excerpts, code and API names. "
                                "Return the complete artifact without adding facts."
                            )
                            continue
                        self._get_model_breaker(provider, model).record_failure(last_code)
                        break
                    self._record_success(provider, model)
                    yield AttemptCompleted(attempt_id)
                    return
                except (TimeoutError, ModelExecutionError) as exc:
                    category = exc.category if isinstance(exc, ModelExecutionError) else ErrorCode.TIMEOUT
                    if category == ErrorCode.TIMEOUT:
                        is_stage_timeout = not isinstance(exc, ModelExecutionError) and (stage_limited_timeout or loop.time() >= budget.deadline)
                        last_code = "STAGE_TIMEOUT" if is_stage_timeout else "MODEL_TIMEOUT"
                        reason = "Model stage deadline exceeded." if is_stage_timeout else "Model attempt timed out."
                    else:
                        last_code = category.value
                        reason = "Model attempt failed: " + last_code
                    yield AttemptFailed(reason, attempt_id, last_code)
                    if text:
                        yield AttemptResetRequired("Discard failed attempt.", attempt_id)
                    if last_code == "STAGE_TIMEOUT":
                        self._get_model_breaker(provider, model).record_failure(last_code)
                        yield RoutingExhausted("Model stage deadline exceeded.", last_code)
                        return
                    if category in (ErrorCode.INVALID_REQUEST, ErrorCode.AUTHENTICATION, ErrorCode.CANCELLED, ErrorCode.UNKNOWN):
                        if provider == "n8n" and category == ErrorCode.AUTHENTICATION:
                            self._get_provider_breaker(provider).record_failure(last_code)
                        yield RoutingExhausted("Terminal provider failure.", last_code)
                        return
                    # Route timeout always opens the model breaker and moves on.
                    if category == ErrorCode.TIMEOUT:
                        self._get_model_breaker(provider, model).record_failure(last_code)
                        break
                    retryable = isinstance(exc, ModelExecutionError) and exc.retryable
                    can_retry = budget.attempts < self.policy.max_total_attempts - (remaining_routes - 1)
                    delay = 2 ** (transport_retries + 1)
                    if (category != ErrorCode.QUOTA_EXHAUSTED and retryable and can_retry
                            and transport_retries < self.policy.max_transport_retries_per_route
                            and route_deadline - loop.time() > delay + 0.05):
                        transport_retries += 1
                        await asyncio.sleep(delay)
                        continue
                    self._get_model_breaker(provider, model).record_failure(last_code)
                    if provider == "n8n":
                        # Model-not-found and model-mismatch are route/model scoped;
                        # provider availability must remain independent. Service,
                        # quota and rate failures are provider scoped for n8n.
                        if category in (ErrorCode.SERVICE_UNAVAILABLE, ErrorCode.QUOTA_EXHAUSTED, ErrorCode.RATE_LIMITED):
                            self._get_provider_breaker(provider).record_failure(last_code)
                        if not self.policy.allow_direct_provider_fallback_after_n8n_failure:
                            if category == ErrorCode.QUOTA_EXHAUSTED:
                                yield RoutingExhausted("n8n provider quota exhausted and bypass is disabled", last_code)
                            else:
                                yield RoutingExhausted("n8n route failed; direct bypass is disabled.", last_code)
                            return
                    break
                except Exception:
                    last_code = "PROVIDER_PROTOCOL_ERROR"
                    yield AttemptFailed("Provider stream failed safely.", attempt_id, last_code)
                    if text:
                        yield AttemptResetRequired("Discard failed attempt.", attempt_id)
                    self._get_model_breaker(provider, model).record_failure(last_code)
                    break
                finally:
                    if stream is not None and hasattr(stream, "aclose"):
                        try:
                            async with asyncio.timeout(0.1):
                                await stream.aclose()
                        except Exception:
                            pass  # Never expose provider cleanup bodies.
        code = "STAGE_TIMEOUT" if loop.time() >= budget.deadline else last_code
        yield RoutingExhausted("All eligible routes or attempt budgets exhausted.", code)
