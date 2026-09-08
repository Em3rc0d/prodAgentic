import json

import pytest

from agents.router import AttemptCompleted, AttemptStarted, ContentChunk
from core.context import GenerationContext, LanguageCode
from core.model_registry import ModelProfile
from core.validator import ArtifactType
from domain.production.models import AgentAttemptStatus, AgentKind, ResearchPackV1, canonical_sha256
from infrastructure.agents.structured_text import StructuredAgentAdapterError, StructuredRouterExecutor


class FixtureRouter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []
        self.calls = 0

    async def stream_generation(self, request):
        self.requests.append(request)
        output = self.outputs[self.calls]
        self.calls += 1
        attempt_id = f"attempt-{self.calls}"
        yield AttemptStarted(model_id="fixture-model", attempt_id=attempt_id, provider="fixture")
        yield ContentChunk(text=output, attempt_id=attempt_id)
        yield AttemptCompleted(attempt_id=attempt_id)


def context():
    return GenerationContext(
        run_id="run-1",
        topic="tech.sql",
        style="question",
        requested_source_language=LanguageCode.AUTO,
        detected_source_language=LanguageCode.UNKNOWN,
        source_detection_confidence=0,
        requested_target_language=LanguageCode.ES,
        resolved_target_language=LanguageCode.ES,
        image_prompt_language=LanguageCode.ES,
    )


def research_json():
    return json.dumps(
        {
            "schema_version": 1,
            "research_id": "research-1",
            "plan_id": "plan-1",
            "verdict": "NO_GO",
            "key_points": [],
            "claims": [],
            "evidence": [],
            "uncertainties": ["No trusted external evidence was supplied."],
            "safety_notes": [],
            "forbidden_claims": [],
            "recommended_angle": None,
        }
    )


@pytest.mark.asyncio
async def test_structured_executor_accepts_only_valid_typed_json_and_records_digest():
    router = FixtureRouter([research_json()])
    executor = StructuredRouterExecutor[ResearchPackV1](router)
    payload = {"plan": {"plan_id": "plan-1"}}
    input_digest = canonical_sha256(payload)

    result = await executor.execute(
        agent=AgentKind.RESEARCH,
        artifact_model=ResearchPackV1,
        artifact_type=ArtifactType.RESEARCH,
        model_profile=ModelProfile.QUALITY_TEXT,
        prompt_version="s3-test-v1",
        system_instruction="fixture",
        input_payload=payload,
        input_digest=input_digest,
        context=context(),
    )

    assert result.artifact.research_id == "research-1"
    assert len(result.attempts) == 1
    assert result.attempts[0].status == AgentAttemptStatus.SUCCESS
    assert result.attempts[0].input_digest == input_digest
    assert result.attempts[0].output_digest == canonical_sha256(result.artifact)
    assert "Return exactly one JSON object" in router.requests[0].user_prompt
    assert "ResearchPackV1" in router.requests[0].user_prompt


@pytest.mark.asyncio
async def test_structured_executor_repairs_once_then_succeeds_with_separate_lineage():
    router = FixtureRouter(["not-json", research_json()])
    executor = StructuredRouterExecutor[ResearchPackV1](router, max_contract_repairs=1)
    input_digest = canonical_sha256({"plan": "fixture"})

    result = await executor.execute(
        agent=AgentKind.RESEARCH,
        artifact_model=ResearchPackV1,
        artifact_type=ArtifactType.RESEARCH,
        model_profile=ModelProfile.QUALITY_TEXT,
        prompt_version="s3-test-v1",
        system_instruction="fixture",
        input_payload={"plan": "fixture"},
        input_digest=input_digest,
        context=context(),
    )

    assert router.calls == 2
    assert [item.status for item in result.attempts] == [
        AgentAttemptStatus.CONTRACT_REPAIR,
        AgentAttemptStatus.SUCCESS,
    ]
    assert result.attempts[0].agent_run_id != result.attempts[1].agent_run_id
    assert "CONTRACT REPAIR" in router.requests[1].user_prompt


@pytest.mark.asyncio
async def test_structured_executor_fails_closed_when_repair_budget_is_exhausted():
    router = FixtureRouter(["{bad", "still bad"])
    executor = StructuredRouterExecutor[ResearchPackV1](router, max_contract_repairs=1)

    with pytest.raises(StructuredAgentAdapterError) as captured:
        await executor.execute(
            agent=AgentKind.RESEARCH,
            artifact_model=ResearchPackV1,
            artifact_type=ArtifactType.RESEARCH,
            model_profile=ModelProfile.QUALITY_TEXT,
            prompt_version="s3-test-v1",
            system_instruction="fixture",
            input_payload={"plan": "fixture"},
            input_digest="e" * 64,
            context=context(),
        )

    assert captured.value.code == "STRUCTURED_REPAIR_EXHAUSTED"
    assert len(captured.value.attempts) == 2
    assert all(item.status == AgentAttemptStatus.CONTRACT_REPAIR for item in captured.value.attempts)
