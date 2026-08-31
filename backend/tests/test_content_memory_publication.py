import copy
from types import SimpleNamespace

import pytest

from core.publication import PublicationCoordinator
from models.content_run import ContentRunStatus


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc):
        self.doc = copy.deepcopy(doc)

    def _get(self, path):
        value = self.doc
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def find_one(self, query):
        if self.doc.get("run_id") != query.get("run_id"):
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update):
        for key, expected in query.items():
            if self._get(key) != expected:
                return UpdateResult(0)
        for key, value in update.get("$set", {}).items():
            target = self.doc
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = copy.deepcopy(value)
        return UpdateResult(1)


class FakeDb:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == "content_runs"
        return self.collection


class FakeConfig:
    author_urn = "urn:li:person:123"
    api_version = "202606"
    access_token = "secret"


class RecordingMemory:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def index_published(self, run_id, approval, external_post_urn):
        self.calls.append((run_id, copy.deepcopy(approval), external_post_urn))
        if self.fail:
            raise RuntimeError("memory unavailable")
        return {"status": "READY"}


def approved_doc():
    return {
        "run_id": "run-memory-publication",
        "workspace_id": "workspace-a",
        "status": ContentRunStatus.APPROVED.value,
        # Deliberately different from immutable approval content. Publication
        # memory must never index this mutable review field.
        "final_content": "mutable review field",
        "approval": {
            "approval_id": "approval-memory-1",
            "bundle_sha256": "bundle-memory-1",
            "final_content": "immutable approved bytes",
            "include_visual": False,
        },
        "publication": None,
    }


@pytest.mark.asyncio
async def test_publication_indexes_only_immutable_approval_content():
    db = FakeDb(approved_doc())
    memory = RecordingMemory()

    class FakePublisher:
        def __init__(self, config):
            assert config.author_urn == FakeConfig.author_urn

        async def publish(self, approval):
            assert approval["final_content"] == "immutable approved bytes"
            return SimpleNamespace(post_urn="urn:li:share:memory-900", image_urn=None)

    coordinator = PublicationCoordinator(
        db,
        publisher_factory=FakePublisher,
        config_factory=lambda: FakeConfig(),
        content_memory=memory,
    )
    updated = await coordinator.publish_run("run-memory-publication")

    assert updated["status"] == ContentRunStatus.PUBLISHED.value
    assert memory.calls == [(
        "run-memory-publication",
        approved_doc()["approval"],
        "urn:li:share:memory-900",
    )]
    assert memory.calls[0][1]["final_content"] != approved_doc()["final_content"]


@pytest.mark.asyncio
async def test_memory_projection_failure_never_rolls_back_confirmed_publication():
    db = FakeDb(approved_doc())
    memory = RecordingMemory(fail=True)

    class FakePublisher:
        def __init__(self, config):
            pass

        async def publish(self, approval):
            return SimpleNamespace(post_urn="urn:li:share:memory-901", image_urn=None)

    coordinator = PublicationCoordinator(
        db,
        publisher_factory=FakePublisher,
        config_factory=lambda: FakeConfig(),
        content_memory=memory,
    )
    updated = await coordinator.publish_run("run-memory-publication")

    assert updated["status"] == ContentRunStatus.PUBLISHED.value
    assert updated["publication"]["external_post_urn"] == "urn:li:share:memory-901"
    assert len(memory.calls) == 1


@pytest.mark.asyncio
async def test_idempotent_published_replay_backfills_memory_without_republishing():
    doc = approved_doc()
    doc["status"] = ContentRunStatus.PUBLISHED.value
    doc["publication"] = {
        "status": "PUBLISHED",
        "bundle_sha256": "bundle-memory-1",
        "external_post_urn": "urn:li:share:already-published",
    }
    db = FakeDb(doc)
    memory = RecordingMemory()

    def forbidden_publisher_factory(config):
        raise AssertionError("publisher must not be constructed for idempotent replay")

    coordinator = PublicationCoordinator(
        db,
        publisher_factory=forbidden_publisher_factory,
        config_factory=lambda: FakeConfig(),
        content_memory=memory,
    )
    updated = await coordinator.publish_run("run-memory-publication")

    assert updated["status"] == ContentRunStatus.PUBLISHED.value
    assert len(memory.calls) == 1
    assert memory.calls[0][2] == "urn:li:share:already-published"
