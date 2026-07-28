import asyncio
from typing import AsyncGenerator
from core.model_registry import ModelProfile, get_models_for_profile
from .adapters.types import ModelExecutionError, ErrorCode, ProviderAdapter

class StageFailedException(Exception):
    """Raised when an attempt fails mid-stream, requiring a full stage reset."""
    pass

class RoutingPolicy:
    max_models_per_stage = 2
    max_retries_per_model = 1
    max_total_attempts = 3

class ModelRouter:
    def __init__(self, google_adapter: ProviderAdapter, n8n_adapter: ProviderAdapter = None):
        self.google_adapter = google_adapter
        self.n8n_adapter = n8n_adapter
        self._circuit_broken_models = set()

    def _get_adapters(self):
        if self.n8n_adapter:
            return [self.n8n_adapter, self.google_adapter]
        return [self.google_adapter]

    async def stream_generation(self, profile: ModelProfile, system_prompt: str, prompt: str, attempt_id: str) -> AsyncGenerator[tuple, None]:
        models = get_models_for_profile(profile)
        total_attempts = 0
        
        for model_def in models:
            if model_def.model_id in self._circuit_broken_models:
                continue
                
            retries = 0
            while retries <= RoutingPolicy.max_retries_per_model and total_attempts < RoutingPolicy.max_total_attempts:
                total_attempts += 1
                successful_start = False
                
                for adapter in self._get_adapters():
                    try:
                        stream_gen = adapter.stream(
                            model=model_def.model_id,
                            prompt=prompt,
                            system_instruction=system_prompt,
                            attempt_id=attempt_id
                        )
                        
                        first = True
                        async for chunk_type, chunk_text in stream_gen:
                            successful_start = True
                            if first:
                                yield ("model_selected", model_def.model_id)
                                first = False
                            yield (chunk_type, chunk_text)
                                
                        return # Success!
                        
                    except ModelExecutionError as exec_error:
                        if successful_start:
                            # Failed mid-stream. We cannot yield an error message as content.
                            print(f"[WARN] Mid-stream failure for {model_def.model_id}: {exec_error}")
                            raise StageFailedException(exec_error)
                        
                        print(f"[WARN] Adapter attempt failed for {model_def.model_id}: {exec_error}")
                        
                        if exec_error.code == ErrorCode.MODEL_NOT_FOUND:
                            self._circuit_broken_models.add(model_def.model_id)
                            
                        if adapter == self._get_adapters()[-1]:
                            # Last adapter failed, apply router retry/fallback logic
                            if exec_error.retryable:
                                retries += 1
                                await asyncio.sleep(2 ** retries)
                                break # Break adapter loop, continue while loop (retry)
                                
                            if exec_error.fallback_allowed:
                                retries = float('inf') # Force break the while loop to move to next model
                                break # Try next model
                                
                            # Terminal error
                            raise exec_error

        raise Exception("All eligible models in profile exhausted or failed.")

    async def generate(self, profile: ModelProfile, system_prompt: str, prompt: str, attempt_id: str) -> tuple:
        models = get_models_for_profile(profile)
        total_attempts = 0
        
        for model_def in models:
            if model_def.model_id in self._circuit_broken_models:
                continue
                
            retries = 0
            while retries <= RoutingPolicy.max_retries_per_model and total_attempts < RoutingPolicy.max_total_attempts:
                total_attempts += 1
                
                for adapter in self._get_adapters():
                    try:
                        res = await adapter.generate(
                            model=model_def.model_id,
                            prompt=prompt,
                            system_instruction=system_prompt,
                            attempt_id=attempt_id
                        )
                        return res.actual_model, res.content
                    except ModelExecutionError as exec_error:
                        print(f"[WARN] Sync adapter attempt failed for {model_def.model_id}: {exec_error}")
                        
                        if exec_error.code == ErrorCode.MODEL_NOT_FOUND:
                            self._circuit_broken_models.add(model_def.model_id)
                            
                        if adapter == self._get_adapters()[-1]:
                            if exec_error.retryable:
                                retries += 1
                                await asyncio.sleep(2 ** retries)
                                break
                                
                            if exec_error.fallback_allowed:
                                retries = float('inf')
                                break
                                
                            raise exec_error
        
        raise Exception("All eligible models in profile exhausted or failed.")
