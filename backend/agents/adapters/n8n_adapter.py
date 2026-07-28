import httpx
from typing import AsyncGenerator
import json

from .types import ProviderAdapter, ModelExecutionResult, ModelExecutionError, ErrorCode

class N8nAdapter(ProviderAdapter):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _translate_error(self, e: Exception) -> ModelExecutionError:
        if isinstance(e, httpx.TimeoutException):
            return ModelExecutionError(ErrorCode.TIMEOUT, "n8n webhook timeout", True, True, e)
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code == 404:
                return ModelExecutionError(ErrorCode.MODEL_NOT_FOUND, "n8n webhook not found", False, True, e)
            elif code == 429:
                return ModelExecutionError(ErrorCode.RATE_LIMITED, "n8n rate limited", True, False, e)
            elif code >= 500:
                return ModelExecutionError(ErrorCode.SERVICE_UNAVAILABLE, f"n8n error: {code}", True, True, e)
            
            return ModelExecutionError(ErrorCode.PROVIDER_PROTOCOL_ERROR, f"n8n HTTP error: {code}", False, False, e)

        return ModelExecutionError(ErrorCode.UNKNOWN, str(e), False, False, e)

    async def generate(self, model: str, prompt: str, **kwargs) -> ModelExecutionResult:
        payload = {
            "model": model,
            "prompt": prompt,
            "attempt_id": kwargs.get("attempt_id", "default")
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(self.webhook_url, json=payload, timeout=90.0)
                res.raise_for_status()
                data = res.json()
                
                actual_model = data.get("actual_model", model)
                text = data.get("text", "")
                
                if actual_model != model:
                    raise ModelExecutionError(
                        ErrorCode.MODEL_MISMATCH,
                        f"Requested model {model} but n8n returned {actual_model}",
                        False, True
                    )
                    
                return ModelExecutionResult(actual_model=actual_model, content=text, raw_response=data)
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e) from e

    async def stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[tuple, None]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "attempt_id": kwargs.get("attempt_id", "default")
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.webhook_url, json=payload, timeout=90.0) as res:
                    res.raise_for_status()
                    
                    async for line in res.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                actual_model = data.get("actual_model", model)
                                if actual_model != model:
                                    raise ModelExecutionError(
                                        ErrorCode.MODEL_MISMATCH,
                                        f"Requested model {model} but n8n returned {actual_model}",
                                        False, True
                                    )
                                chunk_text = data.get("text", "")
                                if chunk_text:
                                    yield ("chunk", chunk_text)
                            except json.JSONDecodeError:
                                pass
        except ModelExecutionError:
            raise
        except Exception as e:
            raise self._translate_error(e) from e
