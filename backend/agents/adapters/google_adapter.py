import traceback
from typing import AsyncGenerator
from google import genai
from google.genai.errors import APIError

from .types import ProviderAdapter, ModelExecutionResult, ModelExecutionError, ErrorCode

class GoogleDirectAdapter(ProviderAdapter):
    def __init__(self, client: genai.Client):
        self.client = client
        self.async_client = client.aio

    def _translate_error(self, e: Exception) -> ModelExecutionError:
        if isinstance(e, APIError):
            code = getattr(e, 'code', 500)
            message = str(e).lower()
            
            if code in (400, 401, 403):
                if code == 400 and "invalid" in message:
                    return ModelExecutionError(ErrorCode.INVALID_REQUEST, str(e), False, False, e)
                return ModelExecutionError(ErrorCode.AUTHENTICATION, str(e), False, False, e)
            elif code == 404:
                return ModelExecutionError(ErrorCode.MODEL_NOT_FOUND, str(e), False, True, e)
            elif code == 429:
                if "quota" in message:
                    return ModelExecutionError(ErrorCode.QUOTA_EXHAUSTED, str(e), False, False, e)
                return ModelExecutionError(ErrorCode.RATE_LIMITED, str(e), True, False, e)
            elif code == 503 or code == 500:
                return ModelExecutionError(ErrorCode.SERVICE_UNAVAILABLE, str(e), True, True, e)
            elif code == 504:
                return ModelExecutionError(ErrorCode.TIMEOUT, str(e), True, True, e)
        
        # Fallback for unknown errors
        if "timeout" in str(e).lower():
            return ModelExecutionError(ErrorCode.TIMEOUT, str(e), True, True, e)
        
        return ModelExecutionError(ErrorCode.UNKNOWN, str(e), False, False, e)

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        try:
            # Base generation
            response = await self.async_client.models.generate_content(
                model=model,
                contents=prompt
            )
            text = response.text if hasattr(response, 'text') else ""
            return ModelExecutionResult(actual_model=model, content=text, raw_response=response)
        except Exception as e:
            raise self._translate_error(e) from e

    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        try:
            response = await self.async_client.models.generate_content_stream(
                model=model,
                contents=prompt
            )
            
            async for chunk in response:
                text = chunk.text if hasattr(chunk, 'text') else ""
                if text:
                    yield ("chunk", text)
        except Exception as e:
            raise self._translate_error(e) from e
