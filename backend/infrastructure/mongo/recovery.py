"""CAS append-only batch recovery ledger, with restart-safe materialization.

The ledger is authority; item/plan inserts are idempotent projections. One atomic
versioned append serializes different replacements in the same batch without
requiring a replica-set transaction or a process-local lock.
"""
from pymongo.errors import DuplicateKeyError

from domain.production.recovery import ReplacementPlanV1, RecoveryConflict
from domain.production.models import canonical_sha256
from infrastructure.mongo.scoped_repository import TenantScopedMongoRepository


class MongoRecoveryRepository:
    def __init__(self, db, context):
        self.context = context
        self.ledgers = TenantScopedMongoRepository(db, "production_recovery_ledgers", context)

    async def read(self, batch_id):
        record = await self.ledgers.find_one({"batch_id": batch_id})
        if record is None:
            return 0, []
        if record.get("version") != len(record.get("entries", [])):
            raise RecoveryConflict("Replacement ledger version mismatch")
        entries = []
        for entry in record["entries"]:
            value = ReplacementPlanV1.model_validate(entry["payload"])
            if (canonical_sha256(value) != entry["digest"] or value.tenant_id != self.context.tenant_id
                    or value.batch_id != batch_id):
                raise RecoveryConflict("Replacement ledger digest mismatch")
            if any(previous.rejected_content_id == value.rejected_content_id
                   or previous.replacement_item.content_id == value.replacement_item.content_id
                   or previous.replacement_plan.plan.candidate_id == value.replacement_plan.plan.candidate_id
                   for previous in entries):
                raise RecoveryConflict("Duplicate replacement authority")
            entries.append(value)
        return record["version"], entries

    async def append(self, version, value: ReplacementPlanV1):
        if value.tenant_id != self.context.tenant_id or version >= 120:
            raise RecoveryConflict("Replacement ledger limit or tenant mismatch")
        entry = {"payload": value.model_dump(mode="json"), "digest": canonical_sha256(value)}
        if version == 0:
            try:
                # Built-in _id uniqueness also protects a concurrent first append.
                await self.ledgers.insert_one({
                    "_id": canonical_sha256({"tenant_id": self.context.tenant_id, "batch_id": value.batch_id}),
                    "batch_id": value.batch_id, "version": 1, "entries": [entry],
                })
                return True
            except DuplicateKeyError:
                return False
        result = await self.ledgers.update_one(
            {"batch_id": value.batch_id, "version": version,
             "entries.payload.rejected_content_id": {"$ne": value.rejected_content_id}},
            {"$inc": {"version": 1}, "$push": {"entries": entry}},
        )
        return result.matched_count == 1

    async def materialize(self, planning, entry):
        plan = entry.replacement_plan
        item = entry.replacement_item
        if plan.content_id != item.content_id or plan.digest != canonical_sha256(plan.plan):
            raise RecoveryConflict("Replacement projection lineage mismatch")
        # Immutable plan first. A crash between writes is repaired from the ledger.
        existing = await planning.get_plan_for_content(item.content_id)
        if existing is None:
            try:
                await planning.plans.insert_one(plan.model_dump())
            except DuplicateKeyError:
                pass
            existing = await planning.get_plan_for_content(item.content_id)
        if existing is None or existing.digest != plan.digest or existing.plan != plan.plan:
            raise RecoveryConflict("Replacement plan projection mismatch")
        current = await planning.get_content_item(item.content_id)
        if current is None:
            try:
                await planning.items.insert_one(item.model_dump())
            except DuplicateKeyError:
                pass
            current = await planning.get_content_item(item.content_id)
        mutable_fields = {"editorial_state", "current_revision_id", "latest_approval_id",
                          "distribution_summary", "created_at", "updated_at"}
        if (current is None or current.model_dump(exclude=mutable_fields) != item.model_dump(exclude=mutable_fields)):
            raise RecoveryConflict("Replacement item projection mismatch")
        return current
