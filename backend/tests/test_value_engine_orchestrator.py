import json
from types import SimpleNamespace

import pytest

import agents.orchestrator as orchestrator_module
from agents.orchestrator import PipelineOrchestrator
from agents.router import ContentChunk
from core.value_engine import sha256_text
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourceType,
)
from models.value_engine import (
    AngleCandidate,
    AngleEngineOutput,
    AttentionCriticAssessment,
    ContentFamily,
)


class DurableRunRepository:
    def __init__(self):
        self.created = None
        self.angle_selection = None
        self.quality = None
        self.text_ready = None

    async def create(self, context, idea, generation_source_packet=None, factual_envelope=None):
        self.created = (context, idea, generation_source_packet, factual_envelope)
        return True

    async def mark_stage_started(self, *args, **kwargs):
        return None

    async def mark_attempt_failed(self, *args, **kwargs):
        return None

    async def mark_stage_completed(self, *args, **kwargs):
        return None

    async def mark_stage_failed(self, *args, **kwargs):
        return None

    async def record_angle_selection(self, run_id, snapshot):
        self.angle_selection = snapshot
        return True

    async def record_content_quality(self, run_id, snapshot):
        self.quality = snapshot
        return True

    async def mark_text_ready(self, run_id, final_content, final_status):
        self.text_ready = (final_content, final_status)
        return True

    async def mark_ready_for_review(self, *args, **kwargs):
        return True

    async def mark_failed(self, *args, **kwargs):
        return None


class NoopMemory:
    async def refresh_review(self, _run_id):
        return None


class StaticAgent:
    def __init__(self, outputs):
        self.outputs = list(outputs) if isinstance(outputs, list) else [outputs]
        self.profile = SimpleNamespace(value="test-profile")
        self.calls = []

    async def stream(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        output = self.outputs[min(len(self.calls) - 1, len(self.outputs) - 1)]
        yield ContentChunk(output, f"attempt-{len(self.calls)}")


class FakeAngleEngine:
    def __init__(self):
        self.calls = []

    async def discover(self, *, idea, research, audience=None, profile_snapshot=None, factual_envelope=None):
        self.calls.append((idea, research, factual_envelope))
        refs = [factual_envelope.allowed_facts[0].statement_id] if factual_envelope else []
        common = dict(
            hook_direction="Open on the proof problem, not on generic AI excitement.",
            reader_tension="Generating is easy; proving approved bytes is harder.",
            reader_payoff="A reusable trust-boundary pattern.",
            evidence_statement_refs=refs,
            audience_relevance=0.9,
            distinctiveness=0.9,
            specificity=0.85,
            profile_curiosity=0.85,
            evidence_density=0.85,
            spam_risk=0.05,
            ai_slop_risk=0.05,
        )
        return AngleEngineOutput(
            output_id="angles-1",
            idea_sha256="a" * 64,
            research_sha256="b" * 64,
            factual_envelope_sha256="c" * 64 if factual_envelope else None,
            engine_version="fake-angle-v1",
            candidates=[
                AngleCandidate(
                    candidate_id="angle:architecture",
                    content_family=ContentFamily.ARCHITECTURE_DECISION,
                    angle="The difficult problem was immutable approval, not text generation.",
                    **common,
                ),
                AngleCandidate(
                    candidate_id="angle:build",
                    content_family=ContentFamily.BUILD_IN_PUBLIC,
                    angle="What the release gate exposed about trust boundaries.",
                    **{**common, "distinctiveness": 0.75},
                ),
                AngleCandidate(
                    candidate_id="angle:insight",
                    content_family=ContentFamily.TECHNICAL_INSIGHT,
                    angle="Why advisory AI needs deterministic authority boundaries.",
                    **{**common, "profile_curiosity": 0.7},
                ),
            ],
        )


class TwoPassCritic:
    def __init__(self, second_pass_good=True):
        self.calls = []
        self.second_pass_good = second_pass_good

    async def critique(self, *, content, pass_number, angle_snapshot=None, profile_snapshot=None):
        self.calls.append((content, pass_number, angle_snapshot))
        strong = pass_number == 2 and self.second_pass_good
        return AttentionCriticAssessment(
            assessment_id=f"quality-{pass_number}",
            content_sha256=sha256_text(content),
            critic_version="fake-critic-v1",
            pass_number=pass_number,
            hook=0.9 if strong else 0.3,
            idea_clarity=0.9,
            novelty=0.8,
            specificity=0.8,
            credibility_signal=0.85,
            narrative_progression=0.8,
            payoff=0.85,
            human_voice=0.85,
            conversation_potential=0.75,
            profile_curiosity=0.75,
            spam_risk=0.05,
            ai_slop_risk=0.05,
            engagement_bait_detected=False,
            generic_opening_detected=False,
            strengths=["specific"],
            rewrite_directives=["Make the first line carry the actual architectural tension."],
        )


def source_packet():
    return SourcePacket(
        packet_id="packet-1",
        workspace_id="workspace-1",
        title="Evidence",
        evidence=[
            EvidenceRef(
                evidence_id="e1",
                authority=SourceAuthority.SYSTEM_DERIVED,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="CI #424 passed all four release gates.",
            )
        ],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-1",
                statement="CI #424 passed all four release gates.",
                source_refs=["e1"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_orchestrator_uses_angle_and_performs_at_most_one_quality_rewrite(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "es")
    monkeypatch.setattr(orchestrator_module, "get_db", lambda: None)

    class MockRouter:
        async def stream_generation(self, *_args, **_kwargs):
            raise AssertionError("Injected agents should handle generation")

    angle_engine = FakeAngleEngine()
    critic = TwoPassCritic(second_pass_good=True)
    orch = PipelineOrchestrator(
        MockRouter(),
        workspace_id="workspace-1",
        angle_engine=angle_engine,
        attention_critic=critic,
    )
    repo = DurableRunRepository()
    research = StaticAgent("research output")
    writer = StaticAgent("draft output")
    editor = StaticAgent(["weak first edit", "strong second edit"])
    orch.content_runs = repo
    orch.content_memory = NoopMemory()
    orch.research_agent = research
    orch.writer_agent = writer
    orch.editor_agent = editor

    events = [
        event
        async for event in orch.run_pipeline_stream(
            "idea",
            "topic",
            "educational",
            content_profile_snapshot={"visual_enabled": False},
            source_packet=source_packet(),
        )
    ]
    payloads = [json.loads(item["data"]) for item in events]

    assert len(angle_engine.calls) == 1
    assert repo.angle_selection is not None
    assert "ANGLE_STRATEGY_DATA" in writer.calls[0][1]["angle_brief"]

    assert len(editor.calls) == 2
    first_envelope = editor.calls[0][1]["factual_envelope"]
    second_envelope = editor.calls[1][1]["factual_envelope"]
    assert first_envelope == second_envelope == writer.calls[0][1]["factual_envelope"]
    assert "QUALITY_REWRITE_DATA" in editor.calls[1][1]["quality_feedback"]

    assert len(critic.calls) == 2
    assert repo.quality is not None
    assert repo.quality.rewrite_performed is True
    assert repo.quality.gate.decision.value == "PASS"
    assert repo.text_ready == ("strong second edit", "READY")

    complete = next(item for item in payloads if item["stage"] == "complete")
    assert complete["final_post"] == "strong second edit"
    assert complete["angle_family"] == "ARCHITECTURE_DECISION"
    assert complete["content_quality_decision"] == "PASS"
    assert complete["quality_rewrite_performed"] is True


@pytest.mark.asyncio
async def test_orchestrator_never_enters_unbounded_quality_rewrite_loop(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LANGUAGE", "es")
    monkeypatch.setattr(orchestrator_module, "get_db", lambda: None)

    class MockRouter:
        async def stream_generation(self, *_args, **_kwargs):
            raise AssertionError("Injected agents should handle generation")

    critic = TwoPassCritic(second_pass_good=False)
    orch = PipelineOrchestrator(
        MockRouter(),
        workspace_id="workspace-1",
        angle_engine=FakeAngleEngine(),
        attention_critic=critic,
    )
    repo = DurableRunRepository()
    orch.content_runs = repo
    orch.content_memory = NoopMemory()
    orch.research_agent = StaticAgent("research")
    orch.writer_agent = StaticAgent("draft")
    editor = StaticAgent(["edit one", "edit two", "must never happen"])
    orch.editor_agent = editor

    events = [
        event
        async for event in orch.run_pipeline_stream(
            "idea",
            "topic",
            "educational",
            content_profile_snapshot={"visual_enabled": False},
            source_packet=source_packet(),
        )
    ]
    payloads = [json.loads(item["data"]) for item in events]

    assert len(editor.calls) == 2
    assert len(critic.calls) == 2
    assert repo.text_ready == ("edit two", "NEEDS_CONTENT_REVIEW")
    complete = next(item for item in payloads if item["stage"] == "complete")
    assert complete["quality_rewrite_performed"] is True
    assert complete["final_status"] == "NEEDS_CONTENT_REVIEW"
