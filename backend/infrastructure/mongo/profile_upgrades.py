from __future__ import annotations

from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from domain.profiles.upgrades import HumanProfileUpgradeDecisionV1
from domain.tenants.models import TenantContext
from infrastructure.mongo.planning import _hydrate_mongo_utc
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


class ProfileUpgradeDecisionConflict(RuntimeError):
    pass


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return _hydrate_mongo_utc(value)


def _same_intent(left: HumanProfileUpgradeDecisionV1, right: HumanProfileUpgradeDecisionV1) -> bool:
    excluded = {"decided_at", "decision_digest"}
    return left.model_dump(mode="json", exclude=excluded) == right.model_dump(mode="json", exclude=excluded)


class MongoProfileUpgradeDecisionRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.decisions = TenantScopedMongoRepository(db, "profile_upgrade_decisions_v1", context)
        self._indexes_ready = False

    async def ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.decisions.collection.create_index(
            [("tenant_id", ASCENDING), ("proposal_id", ASCENDING)],
            unique=True,
            name="tenant_profile_upgrade_decision_unique",
        )
        self._indexes_ready = True

    async def append(self, decision: HumanProfileUpgradeDecisionV1) -> HumanProfileUpgradeDecisionV1:
        await self.ensure_indexes()
        try:
            await self.decisions.insert_one(decision.model_dump(mode="json"))
            return decision
        except DuplicateKeyError:
            existing = await self.get(decision.proposal_id)
            if existing is not None and _same_intent(existing, decision):
                return existing
            raise ProfileUpgradeDecisionConflict("Profile upgrade proposal already has a different decision")

    async def get(self, proposal_id: str) -> HumanProfileUpgradeDecisionV1 | None:
        await self.ensure_indexes()
        raw = _clean(await self.decisions.find_one({"proposal_id": proposal_id}))
        return HumanProfileUpgradeDecisionV1.model_validate(raw) if raw else None
