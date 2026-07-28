from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel
from google import genai

class ModelProfile(str, Enum):
    ECONOMY_TEXT = "ECONOMY_TEXT"
    QUALITY_TEXT = "QUALITY_TEXT"

class ModelStatus(str, Enum):
    STABLE = "STABLE"
    PREVIEW = "PREVIEW"

class ModelDefinition(BaseModel):
    provider: str = "google"
    model_id: str
    status: ModelStatus = ModelStatus.STABLE
    supported_params: List[str] = []

REGISTRY: Dict[ModelProfile, List[ModelDefinition]] = {
    ModelProfile.ECONOMY_TEXT: [
        ModelDefinition(model_id="gemini-3.5-flash-lite", supported_params=["system_instruction"]),
        ModelDefinition(model_id="gemini-3.1-flash-lite", supported_params=["system_instruction"])
    ],
    ModelProfile.QUALITY_TEXT: [
        ModelDefinition(model_id="gemini-3.6-flash", supported_params=["system_instruction"]),
        ModelDefinition(model_id="gemini-3.5-flash", supported_params=["system_instruction"])
    ]
}

import asyncio
from datetime import datetime, timezone, timedelta

# Cache for available models
class PreflightCache:
    def __init__(self):
        self.discoverable_models = set()
        self.checked_at = None
        self.expires_at = None
        self.status_by_model = {}
        self.last_error_category = None
        self.is_valid = False
        self._refresh_lock = asyncio.Lock()
        self.ttl_seconds = 3600

    async def refresh(self, client: genai.Client, force: bool = False):
        if not force and self.is_valid and self.expires_at and datetime.now(timezone.utc) < self.expires_at:
            return

        async with self._refresh_lock:
            if not force and self.is_valid and self.expires_at and datetime.now(timezone.utc) < self.expires_at:
                return
                
            try:
                new_models = set()
                async with asyncio.timeout(10.0):
                    pager = await client.aio.models.list()
                    async for m in pager:
                        name = getattr(m, 'name', '')
                        base_id = getattr(m, 'base_model_id', '')
                        
                        if name: 
                            new_models.add(name.replace("models/", ""))
                        if base_id: 
                            new_models.add(base_id.replace("models/", ""))
                            
                self.discoverable_models = new_models
                self.checked_at = datetime.now(timezone.utc)
                self.expires_at = self.checked_at + timedelta(seconds=self.ttl_seconds)
                self.is_valid = True
                self.last_error_category = None
                print(f"[INFO] Preflight refresh complete. Discovered {len(self.discoverable_models)} models.")
            except TimeoutError:
                self.last_error_category = "TIMEOUT"
                print("[WARN] Preflight refresh failed: Timeout")
            except Exception as e:
                self.last_error_category = str(e)
                print(f"[WARN] Preflight refresh failed: {e}")

_cache = PreflightCache()

async def validate_available_models(client: genai.Client) -> None:
    """Preflight check to discover models available to this API key."""
    await _cache.refresh(client, force=True)

def get_profile_readiness() -> str:
    """Returns READY, DEGRADED, or NOT_READY based on preflight cache."""
    if not _cache.is_valid:
        return "UNKNOWN"
    
    missing_profiles = 0
    degraded_profiles = 0
    
    for profile, definitions in REGISTRY.items():
        available = [d for d in definitions if d.model_id in _cache.discoverable_models]
        if len(available) == 0:
            missing_profiles += 1
        elif len(available) < len(definitions):
            degraded_profiles += 1
            
    is_stale = _cache.expires_at and datetime.now(timezone.utc) > _cache.expires_at
    
    if missing_profiles > 0:
        return "NOT_READY_WITH_STALE_CACHE" if is_stale else "NOT_READY"
    if degraded_profiles > 0:
        return "DEGRADED_WITH_STALE_CACHE" if is_stale else "DEGRADED"
    
    return "READY_WITH_STALE_CACHE" if is_stale else "READY"

def get_models_for_profile(profile: ModelProfile) -> List[ModelDefinition]:
    """Returns the list of models for a given profile, prioritizing those that are discoverable."""
    definitions = REGISTRY.get(profile, [])
    if not _cache.is_valid:
        return definitions # Return all if preflight failed/skipped
    
    return [d for d in definitions if d.model_id in _cache.discoverable_models]

