import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.content_runs as content_run_routes
import routes.scheduling as scheduling_routes
from core.publication import PublicationCoordinator
from core.scheduler import run_due_schedules_once
from core.auth import AuthSettings, SessionManager, router as auth_router, security_boundary
from core.linkedin import LinkedInPublisher
from models.content_run import ContentRunApprovalRequest, ContentRunEditRequest, ContentRunScheduleRequest, ContentRunStatus


class UpdateResult:
    def __init__(self, matched_count: int):
        self.matched_count = matched_count


class FakeCursor:
    def __init__(self, docs):
        self.docs = [copy.deepcopy(doc) for doc in docs]
        self.index = 0

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    def __aiter__(self):
        self.index = 0
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        value = self.docs[self.index]
        self.index += 1
        return value


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = {doc["run_id"]: copy.deepcopy(doc) for doc in (docs or []) if "run_id" in doc}

    @staticmethod
    def _get(doc, path):
        value = doc
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    @classmethod
    def _matches(cls, doc, query):
        for key, expected in query.items():
            actual = cls._get(doc, key)
            if isinstance(expected, dict):
                if "$lte" in expected and not (actual <= expected["$lte"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query):
        for doc in self.docs.values():
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    async def update_one(self, query, update, **_kwargs):
        for run_id, doc in self.docs.items():
            if not self._matches(doc, query):
                continue
            for path, value in update.get("$set", {}).items():
                target = doc
                parts = path.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = copy.deepcopy(value)
            self.docs[run_id] = doc
            return UpdateResult(1)
        return UpdateResult(0)

    def find(self, query):
        return FakeCursor([doc for doc in self.docs.values() if self._matches(doc, query)])


class FakeDb:
    def __init__(self, run):
        self.collections = {
            "content_runs": FakeCollection([run]),
            "posts": FakeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FakeLinkedInConfig:
    author_urn = "urn:li:person:release-test"
    api_version = "202606"
    access_token = "injected-not-a-real-secret"

    @classmethod
    def from_env(cls):
        return cls()


class FakeSchedulingCoordinator:
    def __init__(self, db):
        self.db = db

    async def resolve_config(self):
        return FakeLinkedInConfig()


def generated_run(visual_render=None):
    now = datetime.now(timezone.utc)
    return {
        "run_id": "release-run-001",
        "topic": "Controlled agentic systems",
        "style": "educational",
        "idea": "Why authority boundaries matter",
        "status": ContentRunStatus.READY_FOR_REVIEW.value,
        "content_profile_id": "profile-release-001",
        "content_profile_snapshot": {"version": 1, "display_name": "Release Identity"},
        "stages": {
            name: {"status": "COMPLETED", "output": f"deterministic {name} artifact"}
            for name in ("research", "write", "edit", "visual")
        },
        "final_content": "Generated draft requiring human review.",
        "visual_prompt": "A controlled workflow with explicit authority boundaries",
        "visual_render": visual_render,
        "approval": None,
        "schedule": None,
        "publication": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_release_lifecycle_reopen_edit_approve_schedule_publish_exactly_once(monkeypatch, tmp_path):
    image_bytes = b"release-approved-image-bytes"
    renders = tmp_path / "renders"
    renders.mkdir()
    asset = renders / "release.png"
    asset.write_bytes(image_bytes)
    visual_render = {
        "render_id": "render-release-001",
        "status": "READY",
        "provider": "injected-renderer",
        "asset_url": "/assets/renders/release.png",
        "asset_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "requested_prompt": "A controlled workflow with explicit authority boundaries",
        "prompt_used": "A controlled workflow with explicit authority boundaries",
    }
    db = FakeDb(generated_run(visual_render=visual_render))
    monkeypatch.setattr(content_run_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "PublicationCoordinator", FakeSchedulingCoordinator)

    # Reopen a durable run after the generation session has ended.
    reopened = await content_run_routes.get_content_run("release-run-001")
    assert reopened["content_profile_snapshot"]["version"] == 1
    assert all(stage["status"] == "COMPLETED" for stage in reopened["stages"].values())

    # Human review changes the publishable text without rewriting provenance.
    edited = await content_run_routes.edit_content_run(
        "release-run-001",
        ContentRunEditRequest(final_content="Human-reviewed final content."),
    )
    assert edited["final_content"] == "Human-reviewed final content."
    assert edited["stages"] == reopened["stages"]

    approved = await content_run_routes.approve_content_run(
        "release-run-001",
        ContentRunApprovalRequest(include_visual=True),
    )
    assert approved["status"] == ContentRunStatus.APPROVED.value
    assert approved["approval"]["final_content"] == "Human-reviewed final content."
    assert approved["approval"]["visual_render"]["asset_sha256"] == visual_render["asset_sha256"]
    approved_bundle = approved["approval"]["bundle_sha256"]

    scheduled_for = datetime.now(timezone.utc) + timedelta(hours=1)
    scheduled = await scheduling_routes.schedule_content_run(
        "release-run-001",
        ContentRunScheduleRequest(scheduled_for=scheduled_for),
    )
    assert scheduled["status"] == ContentRunStatus.SCHEDULED.value
    assert scheduled["schedule"]["bundle_sha256"] == approved_bundle

    # Advance only the injected clock evidence; the worker must use the shared coordinator.
    db["content_runs"].docs["release-run-001"]["schedule"]["scheduled_for"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    publish_calls = []

    def linkedin_handler(request: httpx.Request):
        publish_calls.append((request.method, str(request.url)))
        if str(request.url) == "https://api.linkedin.com/rest/images?action=initializeUpload":
            return httpx.Response(200, json={"value": {"uploadUrl": "https://upload.release.test/image", "image": "urn:li:image:release-proof"}})
        if str(request.url) == "https://upload.release.test/image":
            assert request.content == image_bytes
            return httpx.Response(201)
        if str(request.url) == "https://api.linkedin.com/rest/posts":
            body = json.loads(request.content)
            assert body["commentary"] == "Human-reviewed final content."
            assert body["content"]["media"]["id"] == "urn:li:image:release-proof"
            return httpx.Response(201, headers={"x-restli-id": "urn:li:share:release-proof"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(linkedin_handler))

    def publisher_factory(config):
        return LinkedInPublisher(config, client=client, asset_root=str(tmp_path))

    def coordinator_factory(supplied_db):
        return PublicationCoordinator(
            supplied_db,
            publisher_factory=publisher_factory,
            config_factory=FakeLinkedInConfig.from_env,
        )

    assert await run_due_schedules_once(db=db, coordinator_factory=coordinator_factory) == 1
    assert await run_due_schedules_once(db=db, coordinator_factory=coordinator_factory) == 0

    published = await content_run_routes.get_content_run("release-run-001")
    assert published["status"] == ContentRunStatus.PUBLISHED.value
    assert published["schedule"]["status"] == "COMPLETED"
    assert published["publication"]["status"] == "PUBLISHED"
    assert published["publication"]["external_post_urn"] == "urn:li:share:release-proof"
    assert published["publication"]["external_image_urn"] == "urn:li:image:release-proof"
    assert published["publication"]["bundle_sha256"] == approved_bundle
    assert [method for method, _url in publish_calls] == ["POST", "PUT", "POST"]
    await client.aclose()


def test_authenticated_http_reopen_edit_approve_and_schedule(monkeypatch):
    db = FakeDb(generated_run())
    monkeypatch.setattr(content_run_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "PublicationCoordinator", FakeSchedulingCoordinator)

    app = FastAPI()
    auth_settings = AuthSettings(
        enabled=True,
        admin_user="release-admin",
        admin_password="release-password-strong",
        session_secret="release-session-secret-that-is-long-enough",
        ttl_seconds=3600,
        cookie_secure=False,
        cookie_samesite="lax",
    )
    app.state.auth_settings = auth_settings
    app.state.session_manager = SessionManager(auth_settings)
    app.middleware("http")(security_boundary)
    app.include_router(auth_router, prefix="/api")
    app.include_router(content_run_routes.router, prefix="/api")
    app.include_router(scheduling_routes.router, prefix="/api")

    with TestClient(app) as client:
        assert client.get("/api/content-runs/release-run-001").status_code == 401
        login = client.post("/api/auth/login", json={"username": "release-admin", "password": "release-password-strong"})
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        reopened = client.get("/api/content-runs/release-run-001")
        assert reopened.status_code == 200
        assert reopened.json()["status"] == ContentRunStatus.READY_FOR_REVIEW.value

        assert client.patch(
            "/api/content-runs/release-run-001",
            headers=headers,
            json={"final_content": "HTTP-reviewed final content."},
        ).status_code == 200
        approved = client.post(
            "/api/content-runs/release-run-001/approve",
            headers=headers,
            json={"include_visual": False},
        )
        assert approved.status_code == 200
        assert approved.json()["approval"]["final_content"] == "HTTP-reviewed final content."

        scheduled = client.post(
            "/api/content-runs/release-run-001/schedule",
            headers=headers,
            json={"scheduled_for": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        )
        assert scheduled.status_code == 200
        assert scheduled.json()["status"] == ContentRunStatus.SCHEDULED.value


@pytest.mark.asyncio
async def test_approved_visual_tampering_stops_before_external_request(monkeypatch, tmp_path):
    original = b"original-approved-image"
    renders = tmp_path / "renders"
    renders.mkdir()
    asset = renders / "release.png"
    asset.write_bytes(original)
    visual_render = {
        "render_id": "render-release-tamper",
        "status": "READY",
        "provider": "injected-renderer",
        "asset_url": "/assets/renders/release.png",
        "asset_sha256": hashlib.sha256(original).hexdigest(),
        "requested_prompt": "A controlled workflow with explicit authority boundaries",
        "prompt_used": "A controlled workflow with explicit authority boundaries",
    }
    db = FakeDb(generated_run(visual_render=visual_render))
    monkeypatch.setattr(content_run_routes, "get_db", lambda: db)
    approved = await content_run_routes.approve_content_run(
        "release-run-001", ContentRunApprovalRequest(include_visual=True)
    )
    asset.write_bytes(b"tampered-after-approval")
    called = False

    def handler(_request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        publisher = LinkedInPublisher(
            FakeLinkedInConfig(), client=client, asset_root=str(tmp_path)
        )
        with pytest.raises(Exception, match="byte digest"):
            await publisher.publish(approved["approval"])
    assert called is False
