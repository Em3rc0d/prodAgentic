from copy import deepcopy

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from application.tenancy.bootstrap import migrate_bootstrap_tenant
from application.tenancy.context import bootstrap_tenant_id, require_tenant_context
from core.auth import AuthSettings, SessionManager, security_boundary
from core.feature_flags import FeatureFlag, FeatureFlagRegistry
from domain.tenants.models import TenantContext
from infrastructure.mongo.scoped_repository import TenantScopeViolation, TenantScopedMongoRepository


class Result:
    def __init__(self, matched_count=0, modified_count=0):
        self.matched_count = matched_count
        self.modified_count = modified_count


class MemoryCollection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(item) for item in (documents or [])]
        self.last_filter = None

    async def find_one(self, criteria):
        self.last_filter = deepcopy(criteria)
        for document in self.documents:
            if all(document.get(key) == value for key, value in criteria.items()):
                return deepcopy(document)
        return None

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))
        return Result(1, 1)

    async def update_one(self, criteria, update, upsert=False):
        self.last_filter = deepcopy(criteria)
        for document in self.documents:
            if all(document.get(key) == value for key, value in criteria.items()):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                return Result(1, 1)
        if upsert:
            document = deepcopy(criteria)
            document.update(deepcopy(update.get("$setOnInsert", {})))
            self.documents.append(document)
            return Result(0, 0)
        return Result()

    async def update_many(self, criteria, update):
        missing_tenant = criteria == {"tenant_id": {"$exists": False}}
        matched = modified = 0
        for document in self.documents:
            if missing_tenant and "tenant_id" not in document:
                matched += 1
                document.update(deepcopy(update["$set"]))
                modified += 1
        return Result(matched, modified)

    async def count_documents(self, criteria):
        tenant_filter = criteria.get("tenant_id")
        if tenant_filter == {"$exists": False}:
            return sum("tenant_id" not in document for document in self.documents)
        if tenant_filter == {"$exists": True, "$in": [None, ""]}:
            return sum(
                "tenant_id" in document and document.get("tenant_id") in {None, ""}
                for document in self.documents
            )
        return 0


class MemoryDb:
    def __init__(self, documents_by_collection=None):
        documents_by_collection = documents_by_collection or {}
        self.collections = {
            name: MemoryCollection(documents)
            for name, documents in documents_by_collection.items()
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, MemoryCollection())


def test_bootstrap_tenant_id_is_server_deterministic(monkeypatch):
    monkeypatch.delenv("PRODAGENTIC_BOOTSTRAP_TENANT_ID", raising=False)
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "installation-a")
    first = bootstrap_tenant_id()
    assert first == bootstrap_tenant_id()
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "installation-b")
    assert bootstrap_tenant_id() != first


def test_scoped_repository_rejects_cross_tenant_reads_and_writes():
    db = MemoryDb({"profiles": [{"tenant_id": "tenant-a", "profile_id": "a"}]})
    context = TenantContext(tenant_id="tenant-a", actor_id="admin")
    repository = TenantScopedMongoRepository(db, "profiles", context)

    async def assertions():
        found = await repository.find_one({"profile_id": "a"})
        assert found["profile_id"] == "a"
        assert db["profiles"].last_filter == {"tenant_id": "tenant-a", "profile_id": "a"}
        await repository.insert_one({"profile_id": "new"})
        assert db["profiles"].documents[-1]["tenant_id"] == "tenant-a"
        with pytest.raises(TenantScopeViolation):
            await repository.find_one({"tenant_id": "tenant-b", "profile_id": "a"})
        with pytest.raises(TenantScopeViolation):
            await repository.insert_one({"tenant_id": "tenant-b", "profile_id": "b"})
        with pytest.raises(TenantScopeViolation):
            await repository.update_one({"profile_id": "a"}, {"$unset": {"tenant_id": ""}})
        with pytest.raises(TenantScopeViolation):
            await repository.update_one(
                {"profile_id": "a"},
                {"$rename": {"profile_id": "tenant_id.shadow"}},
            )
        with pytest.raises(TenantScopeViolation):
            await repository.update_one({"profile_id": "a"}, {"tenant_id": "tenant-b"})

    import asyncio
    asyncio.run(assertions())


@pytest.mark.asyncio
async def test_bootstrap_migration_is_idempotent_and_preserves_existing_scope(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "migration-test")
    db = MemoryDb({
        "content_profiles": [{"profile_id": "legacy"}],
        "content_runs": [{"run_id": "legacy"}, {"run_id": "other", "tenant_id": "tenant-other"}],
        "posts": [{"post_id": "legacy"}],
        "linkedin_connections": [],
    })

    first = await migrate_bootstrap_tenant(db)
    second = await migrate_bootstrap_tenant(db)
    assert first.verified and second.verified
    assert first.modified_by_collection["content_runs"] == 1
    assert second.modified_by_collection == {
        "content_profiles": 0,
        "content_runs": 0,
        "posts": 0,
        "linkedin_connections": 0,
    }
    assert second.invalid_after_migration == {
        "content_profiles": 0,
        "content_runs": 0,
        "posts": 0,
        "linkedin_connections": 0,
    }
    assert db["content_runs"].documents[1]["tenant_id"] == "tenant-other"
    assert len(db["tenants"].documents) == 1


@pytest.mark.asyncio
async def test_bootstrap_migration_fails_closed_for_invalid_existing_scope(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "invalid-migration-test")
    db = MemoryDb({
        "content_profiles": [
            {"profile_id": "null-scope", "tenant_id": None},
            {"profile_id": "blank-scope", "tenant_id": ""},
        ],
    })

    report = await migrate_bootstrap_tenant(db)

    assert not report.verified
    assert report.modified_by_collection["content_profiles"] == 0
    assert report.invalid_after_migration["content_profiles"] == 2
    assert db["content_profiles"].documents[0]["tenant_id"] is None
    assert db["content_profiles"].documents[1]["tenant_id"] == ""


def test_http_tenant_context_ignores_client_tenant_header(monkeypatch):
    monkeypatch.setenv("PRODAGENTIC_DEPLOYMENT_KEY", "http-test")
    settings = AuthSettings(
        enabled=False,
        admin_user="admin",
        admin_password="",
        session_secret="",
        ttl_seconds=3600,
        cookie_secure=False,
        cookie_samesite="lax",
    )
    app = FastAPI()
    app.state.auth_settings = settings
    app.state.session_manager = SessionManager(settings)
    app.middleware("http")(security_boundary)

    @app.get("/api/mk1/context")
    async def context(request: Request):
        resolved = require_tenant_context(request)
        return {"tenant_id": resolved.tenant_id, "actor_id": resolved.actor_id}

    with TestClient(app) as client:
        response = client.get("/api/mk1/context", headers={"X-Tenant-ID": "tenant-attacker"})
    assert response.status_code == 200
    assert response.json() == {"tenant_id": bootstrap_tenant_id(), "actor_id": "admin"}


def test_feature_registry_is_fail_closed(monkeypatch):
    monkeypatch.setenv("MK1_ENABLED", "false")
    monkeypatch.setenv("MK1_PROFILE_V2", "true")
    registry = FeatureFlagRegistry.from_env()
    assert not registry.enabled(FeatureFlag.MK1_PROFILE_V2)

    monkeypatch.setenv("MK1_ENABLED", "true")
    registry = FeatureFlagRegistry.from_env()
    assert registry.enabled(FeatureFlag.MK1_ENABLED)
    assert registry.enabled(FeatureFlag.MK1_PROFILE_V2)
