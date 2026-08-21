import pytest

import db.content_runs as content_runs_module
from core.context import GenerationContext, LanguageCode
from db.content_runs import ContentRunRepository


class FakeUpdateResult:
    matched_count = 1


class FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, query, update, upsert=False):
        self.calls.append({"query": query, "update": update, "upsert": upsert})
        return FakeUpdateResult()


class FakeDb:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


def context_with_profile():
    snapshot = {
        "profile_id": "profile-1",
        "version": 4,
        "name": "Architect Voice",
        "display_name": "Architect Voice",
        "positioning": "Systems engineering through evidence and implementation.",
        "audience": ["software architects", "engineering leaders"],
        "voice": ["technical", "concise"],
        "core_topics": ["distributed systems", "applied AI"],
        "excluded_topics": ["celebrity news"],
        "min_words": 140,
        "max_words": 210,
        "forbidden_claims": ["invented customer metrics"],
        "banned_phrases": ["game changer"],
        "brand_constraints": ["evidence before persuasion"],
        "visual_enabled": True,
    }
    return GenerationContext(
        run_id="run-1",
        topic="AI systems",
        style="educational",
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.EN,
        source_detection_confidence=1.0,
        requested_target_language=LanguageCode.EN,
        resolved_target_language=LanguageCode.EN,
        image_prompt_language=LanguageCode.EN,
        content_profile_id="profile-1",
        content_profile_snapshot=snapshot,
    )


def test_profile_instructions_include_voice_audience_and_guardrails():
    instructions = context_with_profile().profile_instructions()
    assert "software architects" in instructions
    assert "technical, concise" in instructions
    assert "invented customer metrics" in instructions
    assert "game changer" in instructions
    assert "evidence before persuasion" in instructions
    assert "Do not invent evidence" in instructions


@pytest.mark.asyncio
async def test_content_run_snapshots_exact_profile_version(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(content_runs_module, "get_db", lambda: FakeDb(collection))

    context = context_with_profile()
    created = await ContentRunRepository().create(context, "Durable workflow idea")

    assert created is True
    document = collection.calls[0]["update"]["$setOnInsert"]
    assert document["content_profile_id"] == "profile-1"
    assert document["content_profile_snapshot"]["version"] == 4
    assert document["content_profile_snapshot"]["voice"] == ["technical", "concise"]
