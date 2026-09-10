from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from application.tenancy.context import bootstrap_tenant_id
from domain.publishing.models import (
    ConnectionStatus,
    PublicationReceiptV1,
    PublicationState,
    PublicationV1,
    ScheduleState,
    ScheduleV1,
)
from domain.tenants.models import TenantContext


def _aware(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {key: _aware(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_aware(item) for item in value]
    return value


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return _aware(value)


class MongoScheduleRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.collection = db["schedules_v2"]
        self._indexes_ready = False

    async def _ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index(
            [("tenant_id", 1), ("schedule_id", 1)], unique=True, name="tenant_schedule_unique"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("state", 1), ("scheduled_for", 1)], name="tenant_schedule_due"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("approval_id", 1), ("created_at", -1)], name="tenant_schedule_approval"
        )
        self._indexes_ready = True

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    async def create(self, schedule: ScheduleV1) -> ScheduleV1:
        await self._ensure_indexes()
        if schedule.tenant_id != self.context.tenant_id:
            raise ValueError("Schedule repository tenant authority mismatch")
        payload = schedule.model_dump()
        try:
            await self.collection.insert_one(payload)
            return schedule
        except DuplicateKeyError:
            existing = await self.get(schedule.schedule_id)
            if existing != schedule:
                raise ValueError("immutable ScheduleV1 identity collision")
            return existing

    async def get(self, schedule_id: str) -> ScheduleV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one(self._scope({"schedule_id": schedule_id}))
        return ScheduleV1.model_validate(_clean(raw)) if raw else None

    async def list_due(self, now: datetime, limit: int = 100) -> list[ScheduleV1]:
        await self._ensure_indexes()
        cursor = (
            self.collection.find(
                self._scope({"state": ScheduleState.SCHEDULED.value, "scheduled_for": {"$lte": now}})
            )
            .sort([("scheduled_for", 1), ("schedule_id", 1)])
            .limit(max(1, limit))
        )
        return [ScheduleV1.model_validate(_clean(raw)) async for raw in cursor]

    async def list_window(self, start_at: datetime, end_at: datetime) -> list[ScheduleV1]:
        await self._ensure_indexes()
        cursor = self.collection.find(
            self._scope({"scheduled_for": {"$gte": start_at, "$lt": end_at}})
        ).sort([("scheduled_for", 1), ("schedule_id", 1)])
        return [ScheduleV1.model_validate(_clean(raw)) async for raw in cursor]

    async def list_for_approvals(self, approval_ids: list[str]) -> list[ScheduleV1]:
        await self._ensure_indexes()
        if not approval_ids:
            return []
        cursor = self.collection.find(self._scope({"approval_id": {"$in": list(dict.fromkeys(approval_ids))}}))
        return [ScheduleV1.model_validate(_clean(raw)) async for raw in cursor]

    async def _transition(self, schedule_id: str, *, expected: tuple[ScheduleState, ...], state: ScheduleState, now: datetime, set_fields: dict | None = None) -> ScheduleV1 | None:
        await self._ensure_indexes()
        fields = {"state": state.value, **(set_fields or {})}
        raw = await self.collection.find_one_and_update(
            self._scope({"schedule_id": schedule_id, "state": {"$in": [item.value for item in expected]}}),
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        if raw:
            return ScheduleV1.model_validate(_clean(raw))
        return await self.get(schedule_id)

    async def cancel(self, schedule_id: str, now: datetime) -> ScheduleV1 | None:
        return await self._transition(
            schedule_id,
            expected=(ScheduleState.SCHEDULED,),
            state=ScheduleState.CANCELLED,
            now=now,
            set_fields={"cancelled_at": now},
        )

    async def mark_dispatched(self, schedule_id: str, now: datetime) -> ScheduleV1 | None:
        return await self._transition(
            schedule_id,
            expected=(ScheduleState.SCHEDULED,),
            state=ScheduleState.DISPATCHED,
            now=now,
            set_fields={"dispatched_at": now},
        )

    async def mark_completed(self, schedule_id: str, now: datetime) -> ScheduleV1 | None:
        return await self._transition(
            schedule_id,
            expected=(ScheduleState.DISPATCHED,),
            state=ScheduleState.COMPLETED,
            now=now,
            set_fields={"completed_at": now, "failure_reason": None},
        )

    async def mark_failed(self, schedule_id: str, now: datetime, reason: str) -> ScheduleV1 | None:
        return await self._transition(
            schedule_id,
            expected=(ScheduleState.SCHEDULED, ScheduleState.DISPATCHED),
            state=ScheduleState.FAILED,
            now=now,
            set_fields={"failure_reason": reason[:1000]},
        )


class MongoPublicationRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.collection = db["publications_v2"]
        self._indexes_ready = False

    async def _ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index(
            [("tenant_id", 1), ("publication_id", 1)], unique=True, name="tenant_publication_unique"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("idempotency_key", 1)], unique=True, name="tenant_publication_idempotency"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("schedule_id", 1)], name="tenant_publication_schedule"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("state", 1), ("started_at", 1)], name="tenant_publication_state"
        )
        self._indexes_ready = True

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    async def create(self, publication: PublicationV1) -> PublicationV1:
        await self._ensure_indexes()
        if publication.tenant_id != self.context.tenant_id:
            raise ValueError("Publication repository tenant authority mismatch")
        try:
            await self.collection.insert_one(publication.model_dump())
            return publication
        except DuplicateKeyError:
            existing = await self.get_by_idempotency_key(publication.idempotency_key)
            if existing is None:
                raise
            immutable = (
                existing.approval_id,
                existing.schedule_id,
                existing.provider,
                existing.connection_id,
                existing.destination,
                existing.bundle_sha256,
            )
            candidate = (
                publication.approval_id,
                publication.schedule_id,
                publication.provider,
                publication.connection_id,
                publication.destination,
                publication.bundle_sha256,
            )
            if immutable != candidate:
                raise ValueError("PublicationV1 idempotency identity collision")
            return existing

    async def get(self, publication_id: str) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one(self._scope({"publication_id": publication_id}))
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def get_by_idempotency_key(self, key: str) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one(self._scope({"idempotency_key": key}))
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def claim(self, publication_id: str, *, attempt_id: str, now: datetime) -> tuple[str, PublicationV1 | None]:
        await self._ensure_indexes()
        raw = await self.collection.find_one_and_update(
            self._scope({"publication_id": publication_id, "state": PublicationState.PENDING.value}),
            {"$set": {"state": PublicationState.PUBLISHING.value, "attempt_id": attempt_id, "started_at": now, "safe_error": None, "reconciliation_reason": None}},
            return_document=ReturnDocument.AFTER,
        )
        if raw:
            return "CLAIMED", PublicationV1.model_validate(_clean(raw))
        current = await self.get(publication_id)
        if current is None:
            return "MISSING", None
        mapping = {
            PublicationState.PUBLISHED: "ALREADY_PUBLISHED",
            PublicationState.PUBLISHING: "PUBLISHING",
            PublicationState.FAILED_SAFE: "FAILED_SAFE",
            PublicationState.RECONCILIATION_REQUIRED: "RECONCILIATION_REQUIRED",
        }
        return mapping.get(current.state, "BUSY"), current

    async def mark_published(self, publication_id: str, *, attempt_id: str, receipt: PublicationReceiptV1, now: datetime) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one_and_update(
            self._scope({"publication_id": publication_id, "state": PublicationState.PUBLISHING.value, "attempt_id": attempt_id}),
            {"$set": {
                "state": PublicationState.PUBLISHED.value,
                "external_post_id": receipt.external_post_id,
                "external_asset_ids": list(receipt.external_asset_ids),
                "completed_at": now,
                "receipt_digest": receipt.receipt_digest,
                "safe_error": None,
                "reconciliation_reason": None,
                "provider_receipt": receipt.model_dump(),
            }},
            return_document=ReturnDocument.AFTER,
        )
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def mark_failed_safe(self, publication_id: str, *, attempt_id: str, reason: str, now: datetime) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one_and_update(
            self._scope({"publication_id": publication_id, "state": PublicationState.PUBLISHING.value, "attempt_id": attempt_id}),
            {"$set": {"state": PublicationState.FAILED_SAFE.value, "completed_at": now, "safe_error": reason[:1000], "reconciliation_reason": None}},
            return_document=ReturnDocument.AFTER,
        )
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def mark_reconciliation_required(self, publication_id: str, *, attempt_id: str | None, reason: str, now: datetime, external_post_id: str | None = None, external_asset_ids: tuple[str, ...] = ()) -> PublicationV1 | None:
        await self._ensure_indexes()
        criteria: dict[str, Any] = {
            "publication_id": publication_id,
            "state": {"$in": [PublicationState.PUBLISHING.value, PublicationState.RECONCILIATION_REQUIRED.value]},
        }
        if attempt_id is not None:
            criteria["attempt_id"] = attempt_id
        fields: dict[str, Any] = {
            "state": PublicationState.RECONCILIATION_REQUIRED.value,
            "reconciliation_reason": reason[:1000],
            "completed_at": None,
        }
        if external_post_id:
            fields["external_post_id"] = external_post_id
        if external_asset_ids:
            fields["external_asset_ids"] = list(external_asset_ids)
        raw = await self.collection.find_one_and_update(
            self._scope(criteria), {"$set": fields}, return_document=ReturnDocument.AFTER
        )
        if raw:
            return PublicationV1.model_validate(_clean(raw))
        return await self.get(publication_id)

    async def resolve_reconciliation_published(self, publication_id: str, *, receipt: PublicationReceiptV1, now: datetime) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one_and_update(
            self._scope({"publication_id": publication_id, "state": PublicationState.RECONCILIATION_REQUIRED.value}),
            {"$set": {
                "state": PublicationState.PUBLISHED.value,
                "external_post_id": receipt.external_post_id,
                "external_asset_ids": list(receipt.external_asset_ids),
                "completed_at": now,
                "receipt_digest": receipt.receipt_digest,
                "reconciliation_reason": None,
                "safe_error": None,
                "provider_receipt": receipt.model_dump(),
            }},
            return_document=ReturnDocument.AFTER,
        )
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def resolve_reconciliation_failed_safe(self, publication_id: str, *, reason: str, now: datetime) -> PublicationV1 | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one_and_update(
            self._scope({"publication_id": publication_id, "state": PublicationState.RECONCILIATION_REQUIRED.value}),
            {"$set": {"state": PublicationState.FAILED_SAFE.value, "completed_at": now, "safe_error": reason[:1000], "reconciliation_reason": None}},
            return_document=ReturnDocument.AFTER,
        )
        return PublicationV1.model_validate(_clean(raw)) if raw else None

    async def list_window(self, start_at: datetime, end_at: datetime) -> list[PublicationV1]:
        await self._ensure_indexes()
        cursor = self.collection.find(
            self._scope({"started_at": {"$gte": start_at, "$lt": end_at}})
        ).sort([("started_at", 1), ("publication_id", 1)])
        return [PublicationV1.model_validate(_clean(raw)) async for raw in cursor]

    async def list_for_schedules(self, schedule_ids: list[str]) -> list[PublicationV1]:
        await self._ensure_indexes()
        if not schedule_ids:
            return []
        cursor = self.collection.find(self._scope({"schedule_id": {"$in": list(dict.fromkeys(schedule_ids))}}))
        return [PublicationV1.model_validate(_clean(raw)) async for raw in cursor]


class MongoConnectionRepository:
    def __init__(self, db: Any, context: TenantContext):
        self.context = context
        self.collection = db["connections_v2"]
        self._indexes_ready = False

    async def _ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index(
            [("tenant_id", 1), ("provider", 1)], unique=True, name="tenant_provider_connection_unique"
        )
        await self.collection.create_index(
            [("tenant_id", 1), ("connection_id", 1)], unique=True, name="tenant_connection_id_unique"
        )
        self._indexes_ready = True

    def _scope(self, extra: dict | None = None) -> dict:
        return {"tenant_id": self.context.tenant_id, **(extra or {})}

    @staticmethod
    def _connection_id(tenant_id: str, external_identity: str) -> str:
        digest = hashlib.sha256(f"linkedin|{tenant_id}|{external_identity}".encode("utf-8")).hexdigest()
        return f"conn_{digest[:40]}"

    async def get_linkedin(self) -> dict | None:
        await self._ensure_indexes()
        raw = await self.collection.find_one(self._scope({"provider": "linkedin"}))
        return _clean(raw)

    async def safe_status(self) -> dict:
        connection = await self.get_linkedin()
        if not connection:
            return {"provider": "linkedin", "connected": False, "status": ConnectionStatus.NOT_CONNECTED.value}
        expires_at = _aware(connection.get("expires_at"))
        now = datetime.now(timezone.utc)
        connected = connection.get("status") == ConnectionStatus.CONNECTED.value and isinstance(expires_at, datetime) and expires_at > now
        return {
            "provider": "linkedin",
            "connected": connected,
            "status": ConnectionStatus.CONNECTED.value if connected else ConnectionStatus.RECONNECT_REQUIRED.value,
            "connection_id": connection.get("connection_id"),
            "external_identity": connection.get("external_identity"),
            "display_name": connection.get("display_name"),
            "picture_url": connection.get("picture_url"),
            "scopes": sorted(connection.get("scopes") or []),
            "expires_at": expires_at,
            "connected_at": _aware(connection.get("connected_at")),
            "source": connection.get("source", "s10_oauth"),
        }

    async def upsert_linkedin_oauth(self, *, external_identity: str, display_name: str, picture_url: str | None, encrypted_access_token: str, scopes: list[str], expires_at: datetime, connected_at: datetime) -> dict:
        await self._ensure_indexes()
        connection_id = self._connection_id(self.context.tenant_id, external_identity)
        payload = {
            "tenant_id": self.context.tenant_id,
            "connection_id": connection_id,
            "provider": "linkedin",
            "status": ConnectionStatus.CONNECTED.value,
            "external_identity": external_identity,
            "display_name": display_name,
            "picture_url": picture_url,
            "encrypted_access_token": encrypted_access_token,
            "scopes": sorted(set(scopes)),
            "expires_at": expires_at,
            "connected_at": connected_at,
            "updated_at": connected_at,
            "source": "s10_oauth",
        }
        await self.collection.update_one(
            self._scope({"provider": "linkedin"}),
            {"$set": payload, "$setOnInsert": {"created_at": connected_at}},
            upsert=True,
        )
        return (await self.get_linkedin()) or payload

    async def disconnect_linkedin(self, now: datetime) -> bool:
        await self._ensure_indexes()
        result = await self.collection.update_one(
            self._scope({"provider": "linkedin"}),
            {
                "$set": {"status": ConnectionStatus.NOT_CONNECTED.value, "updated_at": now},
                "$unset": {"encrypted_access_token": ""},
            },
        )
        return result.matched_count == 1

    async def import_legacy_linkedin(self, legacy: dict, *, allow_bootstrap: bool = False) -> dict:
        if not allow_bootstrap or self.context.tenant_id != bootstrap_tenant_id():
            raise ValueError("legacy LinkedIn connection may only migrate into bootstrap tenant authority")
        external_identity = str(legacy.get("author_urn") or "").strip()
        encrypted = str(legacy.get("encrypted_access_token") or "").strip()
        expires_at = _aware(legacy.get("expires_at"))
        connected_at = _aware(legacy.get("connected_at")) or datetime.now(timezone.utc)
        if not external_identity or not encrypted or not isinstance(expires_at, datetime):
            raise ValueError("legacy LinkedIn connection is incomplete")
        existing = await self.get_linkedin()
        if existing is not None:
            return existing
        connection = await self.upsert_linkedin_oauth(
            external_identity=external_identity,
            display_name=str(legacy.get("display_name") or "LinkedIn member"),
            picture_url=legacy.get("picture_url"),
            encrypted_access_token=encrypted,
            scopes=list(legacy.get("scopes") or []),
            expires_at=expires_at,
            connected_at=connected_at,
        )
        await self.collection.update_one(
            self._scope({"provider": "linkedin"}),
            {"$set": {"source": "mk0_bootstrap_migration", "legacy_connection_id": str(legacy.get("_id") or "primary")}},
        )
        return (await self.get_linkedin()) or connection
