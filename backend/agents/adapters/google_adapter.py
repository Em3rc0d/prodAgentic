from typing import AsyncGenerator
from google import genai
from google.genai.errors import APIError

from .types import ProviderAdapter, ModelExecutionResult, ModelExecutionError, ErrorCode


class GoogleDirectAdapter(ProviderAdapter):
    def __init__(self, client: genai.Client):
        self.client = client
        self.async_client = client.aio

    def _translate_error(self, e: Exception, model_id: str, attempt_id: str) -> ModelExecutionError:
        code = getattr(e, "code", 500) if isinstance(e, APIError) else None
        message = str(e).lower()
        http_status = code
        provider_error_code = getattr(e, "status", None) if isinstance(e, APIError) else None

        category = ErrorCode.UNKNOWN
        retryable = False
        fallback_allowed = False

        if isinstance(e, APIError):
            if code in (400, 401, 403):
                if code == 400 and "invalid" in message:
                    category = ErrorCode.INVALID_REQUEST
                else:
                    category = ErrorCode.AUTHENTICATION
            elif code == 404:
                category = ErrorCode.MODEL_NOT_FOUND
                fallback_allowed = True
            elif code == 429:
                if "quota" in message:
                    category = ErrorCode.QUOTA_EXHAUSTED
                else:
                    category = ErrorCode.RATE_LIMITED
                    retryable = True
            elif code in (500, 503):
                category = ErrorCode.SERVICE_UNAVAILABLE
                retryable = True
                fallback_allowed = True
            elif code == 504:
                category = ErrorCode.TIMEOUT
                retryable = True
                fallback_allowed = True
        elif "timeout" in str(e).lower():
            category = ErrorCode.TIMEOUT
            retryable = True
            fallback_allowed = True

        sanitized_message = f"Google API Error: {category.value}"

        return ModelExecutionError(
            category=category,
            provider="google",
            model_id=model_id,
            attempt_id=attempt_id,
            http_status=http_status,
            provider_error_code=str(provider_error_code) if provider_error_code else None,
            retryable=retryable,
            fallback_allowed=fallback_allowed,
            sanitized_message=sanitized_message,
            original_exception=e,
        )

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        attempt_id = kwargs.get("attempt_id", "default")
        profile = kwargs.get("profile_name", "UNKNOWN")
        system_instruction = kwargs.get("system_instruction")
        response_schema = kwargs.get("response_schema")
        response_mime_type = kwargs.get("response_mime_type")
        temperature = kwargs.get("temperature")

        config = None
        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if response_schema is not None:
            # Structured generation is provider-constrained, but downstream code
            # must still validate the returned JSON before trusting it.
            config_kwargs["response_schema"] = response_schema
            config_kwargs["response_mime_type"] = response_mime_type or "application/json"
        elif response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type
        if temperature is not None:
            config_kwargs["temperature"] = temperature

        if config_kwargs:
            from google.genai import types

            config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = await self.async_client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            text = response.text if hasattr(response, "text") and response.text else ""

            if not text or not text.strip():
                raise ModelExecutionError(
                    category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                    provider="google",
                    model_id=model,
                    attempt_id=attempt_id,
                    http_status=None,
                    provider_error_code=None,
                    retryable=False,
                    fallback_allowed=False,
                    sanitized_message="Empty model output received from Google",
                )

            return ModelExecutionResult(
                provider="google",
                requested_model=model,
                actual_model=model,
                model_profile=profile,
                attempt_id=attempt_id,
                content=text,
                finish_reason="STOP",
                raw_response=response,
            )
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e, model, attempt_id) from e

    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        attempt_id = kwargs.get("attempt_id", "default")
        system_instruction = kwargs.get("system_instruction")

        config = None
        if system_instruction:
            from google.genai import types

            config = types.GenerateContentConfig(system_instruction=system_instruction)

        try:
            response = await self.async_client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config=config,
            )

            emitted_content = False
            async for chunk in response:
                text = chunk.text if hasattr(chunk, "text") and chunk.text else ""
                if text and text.strip():
                    emitted_content = True
                    yield ("chunk", text)

            if not emitted_content:
                raise ModelExecutionError(
                    category=ErrorCode.PROVIDER_PROTOCOL_ERROR,
                    provider="google",
                    model_id=model,
                    attempt_id=attempt_id,
                    http_status=None,
                    provider_error_code=None,
                    retryable=False,
                    fallback_allowed=False,
                    sanitized_message="Stream finished without yielding any content",
                )
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e, model, attempt_id) from e
