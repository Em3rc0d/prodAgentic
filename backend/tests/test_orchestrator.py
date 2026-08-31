import json
from types import SimpleNamespace

import pytest

from agents.orchestrator import PipelineOrchestrator
from agents.router import ContentChunk, RoutingExhausted
from models.grounding import (
    EvidenceBoundStatement,
    EvidenceRef,
    SourceAuthority,
    SourcePacket,
    SourceType,
)


class DurableRunRepository:
    async def create(self, context, idea):
        return True

    async def mark_stage_started(self, *args, **kwargs):
        return None

    async def mark_attempt_failed(self, *args, **kwargs):
        return None

    async def mark_stage_completed(self, *args, **kwargs):
        return None

    async def mark_stage_failed(self, *args, **kwargs):
        return None

    async def mark_text_ready(self, *args, **kwargs):
        return None

    async def mark_ready_for_review(self, *args, **kwargs):
        return None

    async def mark_failed(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_orchestrator_stage_failed_exits_pipeline():
    class MockRouter:
        async def stream_generation(self, profile, sys, prompt, run_id):
            yield RoutingExhausted("Failed test")

    orch = PipelineOrchestrator(MockRouter())
    orch.content_runs = DurableRunRepository()

    events = [evt async for evt in orch.run_pipeline_stream("idea", "topic", "style")]

    # Should emit stage.failed, and importantly, it should NOT proceed to the next stage (writer)
    assert any(json.loads(e["data"]).get("stage") == "stage.failed" for e in events)
    assert not any(json.loads(e["data"]).get("stage") == "writer" for e in events)


@pytest.mark.asyncio
async def test_orchestrator_refuses_generation_without_authoritative_content_run():
    router_called = False

    class MockRouter:
        async def stream_generation(self, profile, sys, prompt, run_id):
            nonlocal router_called
            router_called = True
            yield RoutingExhausted("must never execute")

    class UnavailableRunRepository(DurableRunRepository):
        async def create(self, context, idea):
            return False

    orch = PipelineOrchestrator(MockRouter())
    orch.content_runs = UnavailableRunRepository()

    events = [evt async for evt in orch.run_pipeline_stream("idea", "topic", "style")]
    payloads = [json.loads(event["data"]) for event in events]

    assert payloads == [{
        "stage": "pipeline.persistence_failed",
        "reason": "Authoritative ContentRun could not be persisted",
        "run_id": payloads[0]["run_id"],
    }]
    assert router_called is False


@pytest.mark.asyncio
async def test_grounded_generation_snapshots_and_reuses_one_factual_envelope():
    class MockRouter:
        async def stream_generation(self, *_args, **_kwargs):
            raise AssertionError("Injected stage agents should be used instead of the router")

    class CapturingRunRepository(DurableRunRepository):
        def __init__(self):
            self.created = None

        async def create(
            self,
            context,
            idea,
            generation_source_packet=None,
            factual_envelope=None,
        ):
            self.created = {
                "context": context,
                "idea": idea,
                "generation_source_packet": generation_source_packet,
                "factual_envelope": factual_envelope,
            }
            return True

    class CapturingAgent:
        def __init__(self, output):
            self.output = output
            self.profile = SimpleNamespace(value="test-profile")
            self.envelopes = []

        async def stream(self, *_args, factual_envelope=None, **_kwargs):
            self.envelopes.append(factual_envelope)
            yield ContentChunk(self.output, "attempt-1")

    class NoopMemory:
        async def refresh_review(self, _run_id):
            return None

    packet = SourcePacket(
        packet_id="packet-generation",
        workspace_id="workspace-grounded",
        title="Generation evidence",
        evidence=[
            EvidenceRef(
                evidence_id="ev-tests",
                authority=SourceAuthority.SYSTEM_DERIVED,
                source_type=SourceType.CI_EVIDENCE,
                excerpt="150 tests passed and 2 failed.",
            )
        ],
        allowed_facts=[
            EvidenceBoundStatement(
                statement_id="fact-tests",
                statement="Two tests failed after persistence hardening.",
                source_refs=["ev-tests"],
            )
        ],
        allowed_inferences=[
            EvidenceBoundStatement(
                statement_id="inference-lifecycle",
                statement="The failing tests represented an older lifecycle assumption.",
                source_refs=["ev-tests"],
            )
        ],
        prohibited_claims=["Reliability improved by 73 percent."],
    )

    orch = PipelineOrchestrator(MockRouter(), workspace_id="workspace-grounded")
    repository = CapturingRunRepository()
    research = CapturingAgent("research output")
    writer = CapturingAgent("draft output")
    editor = CapturingAgent("final output")
    orch.content_runs = repository
    orch.content_memory = NoopMemory()
    orch.research_agent = research
    orch.writer_agent = writer
    orch.editor_agent = editor

    events = [
        evt
        async for evt in orch.run_pipeline_stream(
            "idea",
            "topic",
            "educational",
            content_profile_snapshot={"visual_enabled": False},
            source_packet=packet,
        )
    ]
    payloads = [json.loads(event["data"]) for event in events]

    assert repository.created is not None
    assert repository.created["generation_source_packet"].packet_id == packet.packet_id
    envelope = repository.created["factual_envelope"]
    assert envelope.packet_id == packet.packet_id
    assert envelope.allowed_facts[0].source_refs == ["ev-tests"]

    assert len(research.envelopes) == 1
    assert research.envelopes == writer.envelopes == editor.envelopes
    rendered_envelope = research.envelopes[0]
    assert "ALLOWED FACTS" in rendered_envelope
    assert "ALLOWED INFERENCES" in rendered_envelope
    assert "PROHIBITED / UNSUPPORTED CLAIMS" in rendered_envelope
    assert "evidence=ev-tests" in rendered_envelope

    complete = next(payload for payload in payloads if payload["stage"] == "complete")
    assert complete["generation_source_packet_id"] == "packet-generation"
    assert complete["factual_envelope_version"] == "factual-envelope-v1"
    assert "generation_source_packet" not in complete
    assert "factual_envelope" not in complete


@pytest.mark.asyncio
async def test_orchestrator_rejects_cross_workspace_generation_packet_before_persistence():
    class MockRouter:
        async def stream_generation(self, *_args, **_kwargs):
            raise AssertionError("Router must not run")

    packet = SourcePacket(
        packet_id="packet-other",
        workspace_id="workspace-other",
        title="Wrong workspace evidence",
        evidence=[
            EvidenceRef(
                evidence_id="ev-1",
                authority=SourceAuthority.USER_PROVIDED,
                source_type=SourceType.PASTED_TEXT,
                excerpt="Evidence",
            )
        ],
    )

    class MustNotCreate(DurableRunRepository):
        async def create(self, *args, **kwargs):
            raise AssertionError("ContentRun must not be created from cross-workspace evidence")

    orch = PipelineOrchestrator(MockRouter(), workspace_id="workspace-a")
    orch.content_runs = MustNotCreate()
    payloads = [
        json.loads(evt["data"])
        async for evt in orch.run_pipeline_stream(
            "idea",
            "topic",
            "educational",
            source_packet=packet,
        )
    ]

    assert len(payloads) == 1
    assert payloads[0]["stage"] == "error"
    assert "workspace" in payloads[0]["reason"].lower()
