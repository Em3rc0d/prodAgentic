import httpx
from typing import AsyncGenerator
import json

from .types import ProviderAdapter, ModelExecutionResult, ModelExecutionError, ErrorCode

class N8nAdapter(ProviderAdapter):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _translate_error(self, e: Exception, model_id: str, attempt_id: str) -> ModelExecutionError:
        category = ErrorCode.UNKNOWN
        retryable = False
        fallback_allowed = False
        http_status = None
        provider_error_code = None

        if isinstance(e, httpx.TimeoutException):
            category = ErrorCode.TIMEOUT
            retryable = True
            fallback_allowed = True
        elif isinstance(e, httpx.HTTPStatusError):
            http_status = e.response.status_code
            if http_status == 404:
                # Si el endpoint no existe, no es un fallback autorizado directo de "MODEL_NOT_FOUND" 
                # pero será N8N_ENDPOINT_NOT_FOUND (SERVICE_UNAVAILABLE).
                category = ErrorCode.SERVICE_UNAVAILABLE
                retryable = True
                fallback_allowed = True
            elif http_status == 429:
                category = ErrorCode.RATE_LIMITED
                retryable = True
            elif http_status >= 500:
                category = ErrorCode.SERVICE_UNAVAILABLE
                retryable = True
                fallback_allowed = True
            else:
                category = ErrorCode.PROVIDER_PROTOCOL_ERROR
        
        sanitized_message = f"n8n API Error: {category.value}"

        return ModelExecutionError(
            category=category,
            provider="n8n",
            model_id=model_id,
            attempt_id=attempt_id,
            http_status=http_status,
            provider_error_code=provider_error_code,
            retryable=retryable,
            fallback_allowed=fallback_allowed,
            sanitized_message=sanitized_message,
            original_exception=e
        )

    def _build_payload(self, model: str, prompt: str, kwargs: dict, stream: bool = False) -> dict:
        return {
            "schema_version": "1.0",
            "correlation_id": kwargs.get("run_id", "default-run"),
            "attempt_id": kwargs.get("attempt_id", "default"),
            "model_profile": kwargs.get("profile_name", "UNKNOWN"),
            "requested_model": model,
            "system_instruction": kwargs.get("system_instruction", ""),
            "user_prompt": prompt,
            "routing_policy_id": "content-default-v1",
            "stream": stream
        }

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        attempt_id = kwargs.get("attempt_id", "default")
        payload = self._build_payload(model, prompt, kwargs, stream=False)
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(self.webhook_url, json=payload, timeout=90.0)
                res.raise_for_status()
                data = res.json()
                
                # Jett: N8N structured error handling
                if "error" in data:
                    err_info = data["error"]
                    cat_str = err_info.get("category", "")
                    if cat_str == "MODEL_NOT_FOUND":
                        raise ModelExecutionError(
                            category=ErrorCode.MODEL_NOT_FOUND,
                            provider="n8n",
                            model_id=model,
                            attempt_id=attempt_id,
                            http_status=res.status_code,
                            provider_error_code=err_info.get("provider_code"),
                            retryable=False,
                            fallback_allowed=True,
                            sanitized_message="n8n reported underlying model not found"
                        )
                
                required_fields = ["schema_version", "provider", "requested_model", "actual_model", "attempt_id", "finish_reason", "content"]
                if not all(field in data for field in required_fields):
                    raise ModelExecutionError(
                        category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                        provider="n8n", model_id=model, attempt_id=attempt_id,
                        http_status=res.status_code, provider_error_code=None,
                        retryable=False, fallback_allowed=False,
                        sanitized_message="Missing required fields in n8n response"
                    )
                
                if data["actual_model"] != model:
                    raise ModelExecutionError(
                        category=ErrorCode.MODEL_MISMATCH,
                        provider="n8n", model_id=model, attempt_id=attempt_id,
                        http_status=res.status_code, provider_error_code=None,
                        retryable=False, fallback_allowed=False,
                        sanitized_message=f"Requested {model} but received {data['actual_model']}"
                    )
                    
                if not data["content"]:
                    raise ModelExecutionError(
                        category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                        provider="n8n", model_id=model, attempt_id=attempt_id,
                        http_status=res.status_code, provider_error_code=None,
                        retryable=False, fallback_allowed=False,
                        sanitized_message="Empty content received from n8n"
                    )
                    
                return ModelExecutionResult(
                    provider=data["provider"],
                    requested_model=data["requested_model"],
                    actual_model=data["actual_model"],
                    model_profile=payload["model_profile"],
                    attempt_id=data["attempt_id"],
                    content=data["content"],
                    finish_reason=data["finish_reason"],
                    raw_response=data
                )
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e, model, attempt_id) from e

    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        attempt_id = kwargs.get("attempt_id", "default")
        payload = self._build_payload(model, prompt, kwargs, stream=True)
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.webhook_url, json=payload, timeout=90.0) as res:
                    res.raise_for_status()
                    
                    has_completed = False
                    async for line in res.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                
                                if data.get("type") == "completed":
                                    actual_model = data.get("actual_model")
                                    if actual_model != model:
                                        raise ModelExecutionError(
                                            category=ErrorCode.MODEL_MISMATCH,
                                            provider="n8n", model_id=model, attempt_id=attempt_id,
                                            http_status=res.status_code, provider_error_code=None,
                                            retryable=False, fallback_allowed=False,
                                            sanitized_message=f"Requested {model} but completed with {actual_model}"
                                        )
                                    has_completed = True
                                    break
                                
                                actual_model = data.get("actual_model")
                                if actual_model and actual_model != model:
                                    raise ModelExecutionError(
                                        category=ErrorCode.MODEL_MISMATCH,
                                        provider="n8n", model_id=model, attempt_id=attempt_id,
                                        http_status=res.status_code, provider_error_code=None,
                                        retryable=False, fallback_allowed=False,
                                        sanitized_message=f"Requested {model} but chunk has {actual_model}"
                                    )
                                chunk_text = data.get("text", "")
                                if chunk_text:
                                    yield ("chunk", chunk_text)
                            except json.JSONDecodeError as jde:
                                raise ModelExecutionError(
                                    category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                                    provider="n8n", model_id=model, attempt_id=attempt_id,
                                    http_status=res.status_code, provider_error_code=None,
                                    retryable=False, fallback_allowed=False,
                                    sanitized_message="Invalid JSON in stream",
                                    original_exception=jde
                                )
                    if not has_completed:
                        raise ModelExecutionError(
                            category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                            provider="n8n", model_id=model, attempt_id=attempt_id,
                            http_status=res.status_code, provider_error_code=None,
                            retryable=False, fallback_allowed=False,
                            sanitized_message="Stream terminated without completed event"
                        )
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e, model, attempt_id) from e
