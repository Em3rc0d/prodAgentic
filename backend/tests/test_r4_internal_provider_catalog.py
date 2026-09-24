from core.internal_provider_catalog import MODEL_CATALOG, TOOL_CAPABILITY_BUCKETS, require_api_model_id
from core.model_registry import ModelProfile, REGISTRY


def test_internal_catalog_covers_observed_provider_console_inventory():
    names = [entry.observed_name for entry in MODEL_CATALOG]
    assert len(names) >= 42
    assert len(names) == len(set(names))
    assert all(entry.internal_only for entry in MODEL_CATALOG)
    assert "Gemini 3.8 Flash" in names
    assert "Gemini 2.5 Flash" in names
    assert "Nano Banana 2 (Gemini 3.1 Flash Image)" in names
    assert "Veo 3 Generate" in names
    assert "Gemini 3.8 Live Extended Thinking" in names
    assert ("Gemini 2.5", "search_grounding") in TOOL_CAPABILITY_BUCKETS


def test_active_routes_resolve_only_verified_api_ids():
    active_ids = {
        definition.model_id
        for definitions in REGISTRY.values()
        for definition in definitions
    }
    catalog_ids = {entry.api_model_id for entry in MODEL_CATALOG if entry.api_model_id}
    assert active_ids <= catalog_ids


def test_evidence_search_has_separate_capability_route():
    evidence_ids = [definition.model_id for definition in REGISTRY[ModelProfile.EVIDENCE_SEARCH]]
    assert evidence_ids == [require_api_model_id("Gemini 2.5 Flash")]
    assert evidence_ids == ["gemini-2.5-flash"]
