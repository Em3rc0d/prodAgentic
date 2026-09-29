from __future__ import annotations

from uuid import uuid4

from pydantic import ValidationError

from domain.production.models import (
    AgentAttemptStatus,
    ContentSpecV1,
    EditorialReviewV1,
    EditorialVerdict,
    ResearchPackV1,
    canonical_sha256,
)
from domain.production.ports import AgentInvocationResult
from infrastructure.agents.structured_text import StructuredAgentAdapterError


_BINDING_FAILURE = "STRUCTURED_CONTRACT_INVALID"


def _bound_result(result: AgentInvocationResult, artifact):
    """Bind SUCCESS lineage to the server-normalized authoritative artifact."""
    digest = canonical_sha256(artifact)
    attempts = tuple(
        attempt.model_copy(update={"output_digest": digest})
        if attempt.status == AgentAttemptStatus.SUCCESS
        else attempt
        for attempt in result.attempts
    )
    return AgentInvocationResult(artifact=artifact, attempts=attempts)


def _raise_binding_error(result: AgentInvocationResult, message: str, exc: Exception) -> None:
    """Turn authority-normalization failures into typed, persistable attempt evidence."""
    attempts = tuple(
        attempt.model_copy(
            update={
                "status": AgentAttemptStatus.FAILED,
                "safe_failure_code": _BINDING_FAILURE,
            }
        )
        if attempt.status == AgentAttemptStatus.SUCCESS
        else attempt
        for attempt in result.attempts
    )
    raise StructuredAgentAdapterError(_BINDING_FAILURE, message, attempts) from exc


class AuthorityBoundResearchAgent:
    """Keep opaque lineage authority out of model-authored ResearchPack fields.

    The model still owns research semantics (verdict, claims, confidence and prose).
    The server owns artifact identity, plan identity and exact acquired-evidence
    metadata. Revalidation after binding keeps unknown claim references fail-closed.
    """

    def __init__(self, delegate):
        self.delegate = delegate

    async def research(self, *, tenant_id, run_id, plan, profile, evidence_bundle=None):
        result = await self.delegate.research(
            tenant_id=tenant_id,
            run_id=run_id,
            plan=plan,
            profile=profile,
            evidence_bundle=evidence_bundle,
        )
        payload = result.artifact.model_dump(mode="python")
        payload["research_id"] = str(uuid4())
        payload["plan_id"] = plan.plan_id
        if evidence_bundle is not None:
            payload["evidence_bundle_ref"] = evidence_bundle.bundle_id
            payload["evidence_bundle_digest"] = canonical_sha256(evidence_bundle)
            payload["evidence"] = [
                source.as_reference().model_dump(mode="python")
                for source in evidence_bundle.sources
            ]
        try:
            artifact = ResearchPackV1.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            _raise_binding_error(
                result,
                "Research output could not be bound to acquired evidence authority",
                exc,
            )
        return _bound_result(result, artifact)


class AuthorityBoundWriterAgent:
    """Server-bind ContentSpec identity and frozen plan identity after generation."""

    def __init__(self, delegate):
        self.delegate = delegate

    async def write(self, *, tenant_id, run_id, plan, profile, research):
        result = await self.delegate.write(
            tenant_id=tenant_id,
            run_id=run_id,
            plan=plan,
            profile=profile,
            research=research,
        )
        payload = result.artifact.model_dump(mode="python")
        payload["content_spec_id"] = str(uuid4())
        payload["plan_id"] = plan.plan_id
        try:
            artifact = ContentSpecV1.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            _raise_binding_error(
                result,
                "Writer output could not be bound to production authority",
                exc,
            )
        return _bound_result(result, artifact)


class AuthorityBoundEditorAgent:
    """Server-bind EditorialReview identity and identities of requested revisions."""

    def __init__(self, delegate):
        self.delegate = delegate

    async def edit(self, *, tenant_id, run_id, plan, profile, research, content, revision_cycle):
        result = await self.delegate.edit(
            tenant_id=tenant_id,
            run_id=run_id,
            plan=plan,
            profile=profile,
            research=research,
            content=content,
            revision_cycle=revision_cycle,
        )
        payload = result.artifact.model_dump(mode="python")
        payload["review_id"] = str(uuid4())
        revised = result.artifact.revised_content_spec
        if result.artifact.verdict == EditorialVerdict.REVISE and revised is not None:
            revised_payload = revised.model_dump(mode="python")
            revised_payload["content_spec_id"] = str(uuid4())
            revised_payload["plan_id"] = plan.plan_id
            payload["revised_content_spec"] = revised_payload
        try:
            artifact = EditorialReviewV1.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            _raise_binding_error(
                result,
                "Editor output could not be bound to production authority",
                exc,
            )
        return _bound_result(result, artifact)
