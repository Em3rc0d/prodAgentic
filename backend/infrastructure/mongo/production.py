from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.production.models import (
    AgentAttemptEvidenceV1,
    ContentRevisionV1,
    GenerationRunV1,
    utc_now,
)
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


def _hydrate_mongo_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return {key: _hydrate_mongo_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_hydrate_mongo_utc(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_hydrate_mongo_utc(item) for item in value)
    return value


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return _hydrate_mongo_utc(value)


class MongoProductionRepository:
    """Durable S3 lineage repository.

    Mongo is the business/evidence authority for GenerationRun lineage. Agents
    receive no collection handle and cannot mutate these records directly.
    """

    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.runs = TenantScopedMongoRepository(db, "generation_runs", context)
        self.attempts = TenantScopedMongoRepository(db, "agent_run_attempts", context)
        self.artifacts = TenantScopedMongoRepository(db, "production_artifacts", context)
        self.revisions = TenantScopedMongoRepository(db, "content_revisions", context)

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.context.tenant_id:
            raise ValueError("Production repository tenant authority mismatch")

    async def create_run(self, run: GenerationRunV1) -> None:
        self._require_tenant(run.tenant_id)
        await self.runs.insert_one(run.model_dump())

    async def get_run(self, tenant_id: str, run_id: str) -> GenerationRunV1 | None:
        self._require_tenant(tenant_id)
        document = _clean(await self.runs.find_one({"run_id": run_id}))
        return GenerationRunV1.model_validate(document) if document else None

    async def update_run(self, run: GenerationRunV1) -> None:
        self._require_tenant(run.tenant_id)
        values = run.model_dump()
        values.pop("tenant_id", None)
        values.pop("run_id", None)
        result = await self.runs.update_one({"run_id": run.run_id}, {"$set": values})
        if result.matched_count != 1:
            raise LookupError("GenerationRun not found")

    async def append_agent_attempt(
        self,
        tenant_id: str,
        run_id: str,
        attempt: AgentAttemptEvidenceV1,
    ) -> None:
        self._require_tenant(tenant_id)
        if await self.get_run(tenant_id, run_id) is None:
            raise LookupError("GenerationRun not found")
        payload = attempt.model_dump()
        payload["run_id"] = run_id
        await self.attempts.insert_one(payload)

    async def save_artifact(
        self,
        *,
        tenant_id: str,
        run_id: str,
        artifact_type: str,
        artifact_id: str,
        digest: str,
        payload: dict,
    ) -> None:
        self._require_tenant(tenant_id)
        if await self.get_run(tenant_id, run_id) is None:
            raise LookupError("GenerationRun not found")
        await self.artifacts.insert_one(
            {
                "artifact_id": artifact_id,
                "run_id": run_id,
                "artifact_type": artifact_type,
                "digest": digest,
                "payload": payload,
                "created_at": utc_now(),
            }
        )

    async def get_artifact(self, tenant_id: str, artifact_id: str) -> dict | None:
        self._require_tenant(tenant_id)
        document = _clean(await self.artifacts.find_one({"artifact_id": artifact_id}))
        return document

    async def list_agent_attempts(self, tenant_id: str, run_id: str) -> list[AgentAttemptEvidenceV1]:
        self._require_tenant(tenant_id)
        documents = await self.attempts.find_many({"run_id": run_id}, sort=[("created_at", 1), ("attempt", 1)])
        values = []
        for document in documents:
            cleaned = _clean(document)
            cleaned.pop("tenant_id", None)
            cleaned.pop("run_id", None)
            values.append(AgentAttemptEvidenceV1.model_validate(cleaned))
        return values

    async def save_revision(self, revision: ContentRevisionV1) -> None:
        self._require_tenant(revision.tenant_id)
        if await self.get_run(revision.tenant_id, revision.run_id) is None:
            raise LookupError("GenerationRun not found")
        await self.revisions.insert_one(revision.model_dump())

    async def get_revision(self, tenant_id: str, revision_id: str) -> ContentRevisionV1 | None:
        self._require_tenant(tenant_id)
        document = _clean(await self.revisions.find_one({"revision_id": revision_id}))
        return ContentRevisionV1.model_validate(document) if document else None
