import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest

from agents.router import ModelRouter, RoutingPolicy
from domain.production.evidence import (
    AcquisitionStatus,
    EvidenceBundleV1,
    EvidenceProvenanceV1,
    EvidenceSourceV1,
)
from domain.production.models import (
    AgentAttemptEvidenceV1,
    AgentAttemptStatus,
    AgentKind,
    ContentSpecV1,
    EditorialCheck,
    EditorialReviewV1,
    EditorialVerdict,
    ResearchPackV1,
    ResearchVerdict,
    canonical_sha256,
    utc_now,
)
from domain.production.ports import AgentInvocationResult
from infrastructure.agents.authority_binding import (
    AuthorityBoundEditorAgent,
    AuthorityBoundResearchAgent,
    AuthorityBoundWriterAgent,
)
from routes.production import (
    R4_EVIDENCE_ATTEMPT_SECONDS,
    R4_EVIDENCE_STAGE_SECONDS,
    R4_PRODUCTION_DEADLINE_SECONDS,
    _evidence_router,
)


class StubAdapter:
    pass


class StaticDelegate:
    def __init__(self, result):
        self.result = result

    async def research(self, **kwargs):
        return self.result

    async def write(self, **kwargs):
        return self.result

    async def edit(self, **kwargs):
        return self.result


def _attempt(agent, artifact):
    return AgentAttemptEvidenceV1(
        agent_run_id=f"attempt-{agent.value.lower()}",
        agent=agent,
        contract_version="structured-v1",
        prompt_version="r4.1-test-v1",
        provider="fixture",
        model="fixture-model",
        attempt=1,
        latency_ms=1,
        input_digest="a" * 64,
        output_digest=canonical_sha256(artifact),
        status=AgentAttemptStatus.SUCCESS,
        created_at=utc_now(),
    )


def _bundle():
    excerpt = "A grounded summary supported by the provider citation metadata."
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    now = utc_now()
    source = EvidenceSourceV1(
        evidence_id="evidence-1",
        locator="https://example.com/source",
        title="Primary source",
        publisher_domain="example.com",
        retrieved_at=now,
        normalized_excerpt=excerpt,
        content_digest=digest,
        provider="fixture",
        provenance=EvidenceProvenanceV1(
            method="grounding",
            model="fixture-model",
            chunk_index=0,
            support_indices=(0,),
        ),
    )
    return EvidenceBundleV1(
        bundle_id="bundle-authority",
        tenant_id="tenant-1",
        plan_id="plan-authority",
        plan_digest="b" * 64,
        sources=(source,),
        acquisition_status=AcquisitionStatus.ACQUIRED,
        query_digest="c" * 64,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_evidence_router_expands_only_the_isolated_evidence_budget():
    google = StubAdapter()
    policy = RoutingPolicy(
        max_stage_seconds=75.0,
        per_attempt_seconds=25.0,
        minimum_fallback_seconds=10.0,
        max_total_attempts=5,
        allow_direct_provider_fallback_after_n8n_failure=True,
    )
    shared = ModelRouter(google_adapter=google, routing_policy=policy)

    evidence = _evidence_router(shared)

    assert evidence is not shared
    assert evidence.google_adapter is google
    assert evidence.policy is not shared.policy
    assert evidence.policy.max_stage_seconds == R4_EVIDENCE_STAGE_SECONDS == 120.0
    assert evidence.policy.per_attempt_seconds == R4_EVIDENCE_ATTEMPT_SECONDS == 120.0
    assert evidence.policy.minimum_fallback_seconds == policy.minimum_fallback_seconds
    assert evidence.policy.max_total_attempts == policy.max_total_attempts
    assert evidence.policy.allow_direct_provider_fallback_after_n8n_failure is True

    assert shared.policy.max_stage_seconds == 75.0
    assert shared.policy.per_attempt_seconds == 25.0
    assert shared.policy.minimum_fallback_seconds == 10.0
    assert R4_PRODUCTION_DEADLINE_SECONDS == 330.0
    assert R4_PRODUCTION_DEADLINE_SECONDS > R4_EVIDENCE_STAGE_SECONDS
    assert R4_PRODUCTION_DEADLINE_SECONDS < 360.0


@pytest.mark.asyncio
async def test_research_authority_is_server_bound_and_unique_per_invocation():
    bundle = _bundle()
    tampered_reference = bundle.sources[0].as_reference().model_copy(
        update={"title": "Model-authored title"}
    )
    model_artifact = ResearchPackV1(
        research_id="model-fixed-research-id",
        plan_id="wrong-plan",
        verdict=ResearchVerdict.GO,
        key_points=("Useful supported point",),
        evidence=(tampered_reference,),
        evidence_bundle_ref="wrong-bundle",
        evidence_bundle_digest="0" * 64,
    )
    result = AgentInvocationResult(
        artifact=model_artifact,
        attempts=(_attempt(AgentKind.RESEARCH, model_artifact),),
    )
    agent = AuthorityBoundResearchAgent(StaticDelegate(result))
    plan = SimpleNamespace(plan_id=bundle.plan_id)

    first = await agent.research(
        tenant_id=bundle.tenant_id,
        run_id="run-1",
        plan=plan,
        profile=object(),
        evidence_bundle=bundle,
    )
    second = await agent.research(
        tenant_id=bundle.tenant_id,
        run_id="run-2",
        plan=plan,
        profile=object(),
        evidence_bundle=bundle,
    )

    assert first.artifact.research_id != "model-fixed-research-id"
    assert first.artifact.research_id != second.artifact.research_id
    assert first.artifact.plan_id == bundle.plan_id
    assert first.artifact.evidence_bundle_ref == bundle.bundle_id
    assert first.artifact.evidence_bundle_digest == canonical_sha256(bundle)
    assert first.artifact.evidence == (bundle.sources[0].as_reference(),)
    assert first.attempts[-1].output_digest == canonical_sha256(first.artifact)


@pytest.mark.asyncio
async def test_writer_and_editor_artifact_ids_are_server_owned():
    plan = SimpleNamespace(plan_id="plan-authority")
    content = ContentSpecV1(
        content_spec_id="model-fixed-content-id",
        plan_id="wrong-plan",
        language="es",
        hook="Hook",
        body="Body",
        format="text",
        format_spec={"kind": "text"},
    )
    writer_result = AgentInvocationResult(
        artifact=content,
        attempts=(_attempt(AgentKind.WRITER, content),),
    )
    writer = AuthorityBoundWriterAgent(StaticDelegate(writer_result))

    bound_content = await writer.write(
        tenant_id="tenant-1",
        run_id="run-1",
        plan=plan,
        profile=object(),
        research=object(),
    )

    assert bound_content.artifact.content_spec_id != "model-fixed-content-id"
    assert bound_content.artifact.plan_id == plan.plan_id
    assert bound_content.attempts[-1].output_digest == canonical_sha256(bound_content.artifact)

    review = EditorialReviewV1(
        review_id="model-fixed-review-id",
        verdict=EditorialVerdict.APPROVE_TEXT,
        brand_match=EditorialCheck.PASS,
        clarity=EditorialCheck.PASS,
        hook_strength=EditorialCheck.PASS,
        factual_consistency=EditorialCheck.PASS,
        platform_fit=EditorialCheck.PASS,
    )
    editor_result = AgentInvocationResult(
        artifact=review,
        attempts=(_attempt(AgentKind.EDITOR, review),),
    )
    editor = AuthorityBoundEditorAgent(StaticDelegate(editor_result))

    bound_review = await editor.edit(
        tenant_id="tenant-1",
        run_id="run-1",
        plan=plan,
        profile=object(),
        research=object(),
        content=bound_content.artifact,
        revision_cycle=0,
    )

    assert bound_review.artifact.review_id != "model-fixed-review-id"
    assert bound_review.attempts[-1].output_digest == canonical_sha256(bound_review.artifact)
