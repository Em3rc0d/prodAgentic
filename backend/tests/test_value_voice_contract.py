import pytest

from agents.content_writer import ContentWriterAgent, SYSTEM_PROMPT as WRITER_SYSTEM_PROMPT
from agents.editor_agent import EditorAgent, SYSTEM_PROMPT as EDITOR_SYSTEM_PROMPT
from agents.idea_generator import SYSTEM_PROMPT as IDEA_SYSTEM_PROMPT
from agents.router import AttemptCompleted, AttemptStarted, ContentChunk
from core.context import GenerationContext, LanguageCode


class CapturingRouter:
    def __init__(self):
        self.requests = []

    async def stream_generation(self, request):
        self.requests.append(request)
        if False:
            yield None


class MarkdownEditorRouter:
    async def stream_generation(self, request):
        yield AttemptStarted("gemini-test", "attempt-plain-text", "google")
        yield ContentChunk(r"Tratar el \*grounding\* con **Zero Trust** y `GroundingPolicy`.", "attempt-plain-text")
        yield AttemptCompleted("attempt-plain-text")


class CompletionlessEditorRouter:
    async def stream_generation(self, request):
        yield ContentChunk(r"Contenido guardado con \*grounding\* y **plain text**.", "attempt-no-completion")


def context(style: str) -> GenerationContext:
    return GenerationContext(
        run_id="run-voice",
        workspace_id="workspace-voice",
        topic="AI systems",
        style=style,
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.ES,
        source_detection_confidence=0.99,
        requested_target_language=LanguageCode.ES,
        resolved_target_language=LanguageCode.ES,
        image_prompt_language=LanguageCode.EN,
    )


def test_idea_generator_forbids_fake_autobiography_and_manufactured_incidents():
    prompt = IDEA_SYSTEM_PROMPT.lower()

    assert "never invent first-person experiences" in prompt
    assert "idea generation currently receives no such evidence" in prompt
    assert "the day we" in prompt
    assert "i spent three days" in prompt
    assert "manufactured outrage" in prompt


def test_writer_uses_narrative_design_instead_of_fixed_content_marketing_template():
    prompt = WRITER_SYSTEM_PROMPT.lower()

    assert "narrative design" in prompt
    assert "never force every post into the same template" in prompt
    assert "cta are not mandatory sections" in prompt
    assert "do not default to \"three reasons\"" in prompt
    assert "required structure" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("style", "expected_fragment"),
    [
        ("educational", "Teach through mechanism and reasoning"),
        ("storytelling", "assumption → tension → realization → principle"),
        ("controversial", "Take a crisp, defensible technical stance"),
    ],
)
async def test_writer_maps_actual_create_studio_style_values(style, expected_fragment):
    router = CapturingRouter()
    agent = ContentWriterAgent(router)

    events = [
        event
        async for event in agent.stream(
            "A technical idea",
            "Research notes",
            context=context(style),
        )
    ]

    assert events == []
    assert len(router.requests) == 1
    assert expected_fragment in router.requests[0].user_prompt


def test_editor_does_not_force_numbered_lists_or_generic_cta():
    prompt = EDITOR_SYSTEM_PROMPT.lower()

    assert "do not impose a content-marketing template" in prompt
    assert "a question is optional, not required" in prompt
    assert "¿qué opinas?" in prompt
    assert "do not turn a technically interesting post into influencer copy" in prompt


def test_editor_declares_plain_linkedin_text_and_intellectual_storytelling_contract():
    prompt = EDITOR_SYSTEM_PROMPT.lower()

    assert "plain unicode text" in prompt
    assert "do not use markdown emphasis" in prompt
    assert "escaped emphasis" in prompt
    assert "assumption → tension → changed model → engineering consequence" in prompt
    assert "encyclopedic exposition" in prompt


@pytest.mark.asyncio
async def test_editor_withholds_raw_markdown_and_emits_only_normalized_final_chunk():
    agent = EditorAgent(MarkdownEditorRouter())

    events = [
        event
        async for event in agent.stream(
            "Draft",
            context=context("storytelling"),
        )
    ]

    chunks = [event.text for event in events if isinstance(event, ContentChunk)]

    assert chunks == ["Tratar el grounding con Zero Trust y GroundingPolicy."]
    assert any(isinstance(event, AttemptStarted) for event in events)
    assert any(isinstance(event, AttemptCompleted) for event in events)


@pytest.mark.asyncio
async def test_editor_flushes_normalized_content_when_stream_ends_without_completion_event():
    agent = EditorAgent(CompletionlessEditorRouter())

    events = [
        event
        async for event in agent.stream(
            "Draft",
            context=context("storytelling"),
        )
    ]

    chunks = [event.text for event in events if isinstance(event, ContentChunk)]

    assert chunks == ["Contenido guardado con grounding y plain text."]
    assert not any(isinstance(event, AttemptCompleted) for event in events)
