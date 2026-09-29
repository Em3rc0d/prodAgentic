from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from domain.learning.proposals import HumanProfileDecisionV1, LearningProposalV1
from domain.tenants.models import TenantContext
from infrastructure.mongo.planning import _hydrate_mongo_utc
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


class LearningProposalPersistenceConflict(RuntimeError):
    pass


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return _hydrate_mongo_utc(value)


def _same_decision_intent(left: HumanProfileDecisionV1, right: HumanProfileDecisionV1) -> bool:
    excluded = {"decided_at", "decision_digest"}
    return left.model_dump(mode="json", exclude=excluded) == right.model_dump(mode="json", exclude=excluded)


class MongoLearningProposalRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.proposals = TenantScopedMongoRepository(db, "learning_proposals_v1", context)
        self.decisions = TenantScopedMongoRepository(db, "learning_profile_decisions_v1", context)
        self._indexes_ready = False

    async def ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.proposals.collection.create_index(
            [("tenant_id", ASCENDING), ("proposal_id", ASCENDING)],
            unique=True,
            name="tenant_learning_proposal_unique",
        )
        await self.proposals.collection.create_index(
            [("tenant_id", ASCENDING), ("profile_id", ASCENDING), ("created_at", DESCENDING)],
            name="tenant_profile_learning_proposals",
        )
        await self.decisions.collection.create_index(
            [("tenant_id", ASCENDING), ("proposal_id", ASCENDING)],
            unique=True,
            name="tenant_learning_proposal_decision_unique",
        )
        self._indexes_ready = True

    async def append(self, proposal: LearningProposalV1) -> LearningProposalV1:
        await self.ensure_indexes()
        try:
            await self.proposals.insert_one(proposal.model_dump(mode="json"))
            return proposal
        except DuplicateKeyError:
            existing = await self.get(proposal.proposal_id)
            if existing is not None and existing.proposal_digest == proposal.proposal_digest:
                return existing
            raise LearningProposalPersistenceConflict(
                "Learning proposal identity already exists with different authority"
            )

    async def get(self, proposal_id: str) -> LearningProposalV1 | None:
        await self.ensure_indexes()
        raw = _clean(await self.proposals.find_one({"proposal_id": proposal_id}))
        return LearningProposalV1.model_validate(raw) if raw else None

    async def list_for_profile(self, profile_id: str) -> list[LearningProposalV1]:
        await self.ensure_indexes()
        documents = await self.proposals.find_many(
            {"profile_id": profile_id},
            sort=[("created_at", DESCENDING), ("proposal_id", ASCENDING)],
        )
        return [LearningProposalV1.model_validate(_clean(item)) for item in documents]

    async def append_decision(self, decision: HumanProfileDecisionV1) -> HumanProfileDecisionV1:
        await self.ensure_indexes()
        try:
            await self.decisions.insert_one(decision.model_dump(mode="json"))
            return decision
        except DuplicateKeyError:
            existing = await self.get_decision(decision.proposal_id)
            if existing is not None and _same_decision_intent(existing, decision):
                return existing
            raise LearningProposalPersistenceConflict(
                "Learning proposal already has a different decision intent"
            )

    async def get_decision(self, proposal_id: str) -> HumanProfileDecisionV1 | None:
        await self.ensure_indexes()
        raw = _clean(await self.decisions.find_one({"proposal_id": proposal_id}))
        return HumanProfileDecisionV1.model_validate(raw) if raw else None
