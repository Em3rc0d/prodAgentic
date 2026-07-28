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

# Cache for available models
_discoverable_models = set()
_preflight_done = False

async def validate_available_models(client: genai.Client) -> None:
    """Preflight check to discover models available to this API key."""
    global _discoverable_models, _preflight_done
    try:
        _discoverable_models = set()
        
        # Use sync generator since this runs once at startup
        for m in client.models.list():
            name = getattr(m, 'name', '')
            base_id = getattr(m, 'base_model_id', '')
            
            if name: 
                _discoverable_models.add(name.replace("models/", ""))
            if base_id: 
                _discoverable_models.add(base_id.replace("models/", ""))
                
        _preflight_done = True
        print(f"[INFO] Preflight complete. Discovered {len(_discoverable_models)} models.")
    except Exception as e:
        print(f"[WARN] Preflight failed: {e}")
        _preflight_done = False

def get_profile_readiness() -> str:
    """Returns READY, DEGRADED, or NOT_READY based on preflight cache."""
    if not _preflight_done:
        return "UNKNOWN"
    
    missing_profiles = 0
    degraded_profiles = 0
    
    for profile, definitions in REGISTRY.items():
        available = [d for d in definitions if d.model_id in _discoverable_models]
        if len(available) == 0:
            missing_profiles += 1
        elif len(available) < len(definitions):
            degraded_profiles += 1
            
    if missing_profiles > 0:
        return "NOT_READY"
    if degraded_profiles > 0:
        return "DEGRADED"
    return "READY"

def get_models_for_profile(profile: ModelProfile) -> List[ModelDefinition]:
    """Returns the list of models for a given profile, prioritizing those that are discoverable."""
    definitions = REGISTRY.get(profile, [])
    if not _preflight_done:
        return definitions # Return all if preflight failed/skipped
    
    return [d for d in definitions if d.model_id in _discoverable_models]
