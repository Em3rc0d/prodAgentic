import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import routes.content_runs as content_run_routes
import routes.scheduling as scheduling_routes
from core.publication import PublicationCoordinator
from core.scheduler import run_due_schedules_once
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


def generated_run():
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
        "visual_render": None,
        "approval": None,
        "schedule": None,
        "publication": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_release_lifecycle_reopen_edit_approve_schedule_publish_exactly_once(monkeypatch):
    db = FakeDb(generated_run())
    monkeypatch.setattr(content_run_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "get_db", lambda: db)
    monkeypatch.setattr(scheduling_routes, "LinkedInPublisherConfig", FakeLinkedInConfig)

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
        ContentRunApprovalRequest(include_visual=False),
    )
    assert approved["status"] == ContentRunStatus.APPROVED.value
    assert approved["approval"]["final_content"] == "Human-reviewed final content."
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

    class InjectedPublisher:
        def __init__(self, config):
            assert config.author_urn == FakeLinkedInConfig.author_urn

        async def publish(self, approval):
            publish_calls.append(approval["bundle_sha256"])
            return SimpleNamespace(post_urn="urn:li:share:release-proof", image_urn=None)

    def coordinator_factory(supplied_db):
        return PublicationCoordinator(
            supplied_db,
            publisher_factory=InjectedPublisher,
            config_factory=FakeLinkedInConfig.from_env,
        )

    assert await run_due_schedules_once(db=db, coordinator_factory=coordinator_factory) == 1
    assert await run_due_schedules_once(db=db, coordinator_factory=coordinator_factory) == 0

    published = await content_run_routes.get_content_run("release-run-001")
    assert published["status"] == ContentRunStatus.PUBLISHED.value
    assert published["schedule"]["status"] == "COMPLETED"
    assert published["publication"]["status"] == "PUBLISHED"
    assert published["publication"]["external_post_urn"] == "urn:li:share:release-proof"
    assert published["publication"]["bundle_sha256"] == approved_bundle
    assert publish_calls == [approved_bundle]
