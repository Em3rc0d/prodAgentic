"""Internal provider model inventory.

This module is server-side routing metadata. It must never be serialized into
customer-facing responses, prompts, browser bundles, or public diagnostics.

The inventory mirrors the provider console observed for the prodAgentic project.
Provider availability and quota are dynamic and must be resolved at runtime;
this file is not a quota authority.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternalModelCatalogEntry:
    observed_name: str
    category: str
    api_model_id: str | None = None
    internal_only: bool = True
    notes: str | None = None


MODEL_CATALOG: tuple[InternalModelCatalogEntry, ...] = (
    InternalModelCatalogEntry("Gemini 3.6 Flash", "text", "gemini-3.6-flash"),
    InternalModelCatalogEntry("Gemini 3.5 Flash", "text", "gemini-3.5-flash"),
    InternalModelCatalogEntry("Gemini 3.5 Flash Lite", "text", "gemini-3.5-flash-lite"),
    InternalModelCatalogEntry("Gemini 3.1 Flash Lite", "text", "gemini-3.1-flash-lite"),
    InternalModelCatalogEntry("Antigravity", "agent"),
    InternalModelCatalogEntry("Deep Research Pro Preview", "agent"),
    InternalModelCatalogEntry("Gemini 2 Flash", "text"),
    InternalModelCatalogEntry("Gemini 2 Flash Lite", "text"),
    InternalModelCatalogEntry("Computer Use Preview", "specialized"),
    InternalModelCatalogEntry("Gemini 2.5 Flash", "text", "gemini-2.5-flash",
                              notes="Grounded Google Search verified in R4.1 UAT."),
    InternalModelCatalogEntry("Nano Banana (Gemini 2.5 Flash Preview Image)", "image"),
    InternalModelCatalogEntry("Gemini 2.5 Flash Lite", "text", "gemini-2.5-flash-lite",
                              notes="Current project probe returned provider NOT_FOUND for new users."),
    InternalModelCatalogEntry("Gemini 2.5 Flash TTS", "tts"),
    InternalModelCatalogEntry("Gemini 2.5 Pro", "text"),
    InternalModelCatalogEntry("Gemini 2.5 Pro TTS", "tts"),
    InternalModelCatalogEntry("Gemini 3 Flash", "text"),
    InternalModelCatalogEntry("Nano Banana Pro (Gemini 3 Pro Image)", "image"),
    InternalModelCatalogEntry("Gemini 3.1 Pro", "text"),
    InternalModelCatalogEntry("Nano Banana 2 (Gemini 3.1 Flash Image)", "image", "gemini-3.1-flash-image"),
    InternalModelCatalogEntry("Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image)", "image"),
    InternalModelCatalogEntry("Gemini 3.1 Flash TTS", "tts"),
    InternalModelCatalogEntry("Gemini 3.5 Transcribe", "transcription"),
    InternalModelCatalogEntry("Gemini 3.7 Flash", "text", "gemini-3.7-flash"),
    InternalModelCatalogEntry("Gemini 3.8 Flash", "text", "gemini-3.8-flash"),
    InternalModelCatalogEntry("Gemini Embedding 1", "embedding"),
    InternalModelCatalogEntry("Gemini Embedding 2", "embedding"),
    InternalModelCatalogEntry("Gemini Omni 1.1 Flash", "multimodal"),
    InternalModelCatalogEntry("Gemini Omni Flash", "multimodal"),
    InternalModelCatalogEntry("Gemini Robotics ER 2 Preview", "robotics"),
    InternalModelCatalogEntry("Gemma 4 26B", "open_model"),
    InternalModelCatalogEntry("Gemma 4 31B", "open_model"),
    InternalModelCatalogEntry("Lyria 3 Clip", "music"),
    InternalModelCatalogEntry("Lyria 3 Pro", "music"),
    InternalModelCatalogEntry("Veo 3 Fast Generate", "video"),
    InternalModelCatalogEntry("Veo 3 Generate", "video"),
    InternalModelCatalogEntry("Veo 3 Lite Generate", "video"),
    InternalModelCatalogEntry("Gemini 2.5 Flash Native Audio Dialog", "live_audio"),
    InternalModelCatalogEntry("Gemini 3 Flash Live", "live_audio"),
    InternalModelCatalogEntry("Gemini 3.5 Live Translate", "live_audio"),
    InternalModelCatalogEntry("Gemini 3.5 Transcribe Live", "live_audio"),
    InternalModelCatalogEntry("Gemini 3.8 Live", "live_audio"),
    InternalModelCatalogEntry("Gemini 3.8 Live Extended Thinking", "live_audio"),
)


# Provider-console tool capability buckets observed alongside the model inventory.
# These are informational only: quota values are deliberately not persisted here.
TOOL_CAPABILITY_BUCKETS: tuple[tuple[str, str], ...] = (
    ("Deep Research Pro Preview", "assignment_grounding"),
    ("Gemini 2 Flash", "assignment_grounding"),
    ("Computer Use Preview", "assignment_grounding"),
    ("Gemini 2.5 Flash", "assignment_grounding"),
    ("Gemini 2.5 Flash Lite", "assignment_grounding"),
    ("Gemini 2.5 Pro", "assignment_grounding"),
    ("Gemini 3 Flash", "assignment_grounding"),
    ("Gemini 3.1 Pro", "assignment_grounding"),
    ("Gemini 3.1 Flash Lite", "assignment_grounding"),
    ("Gemini 3.1 Flash TTS", "assignment_grounding"),
    ("Gemini 3.5 Flash", "assignment_grounding"),
    ("Gemini 3.5 Flash Lite", "assignment_grounding"),
    ("Gemini 3.5 Transcribe", "assignment_grounding"),
    ("Gemini 3.6 Flash", "assignment_grounding"),
    ("Gemini 3.7 Flash", "assignment_grounding"),
    ("Gemini 3.8 Flash", "assignment_grounding"),
    ("Gemini Robotics ER 2 Preview", "assignment_grounding"),
    ("Gemini 2", "search_grounding"),
    ("Gemini 2.5", "search_grounding"),
    ("Gemini 3", "search_grounding"),
    ("Default", "search_grounding"),
)


def require_api_model_id(observed_name: str) -> str:
    """Resolve only explicitly known API ids; never infer provider identifiers."""
    for entry in MODEL_CATALOG:
        if entry.observed_name == observed_name:
            if entry.api_model_id is None:
                raise LookupError(f"No verified API model id for internal catalog entry: {observed_name}")
            return entry.api_model_id
    raise LookupError(f"Unknown internal catalog entry: {observed_name}")
