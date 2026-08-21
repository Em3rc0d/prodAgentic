import copy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import routes.scheduling as scheduling_routes
from core.scheduler import run_due_schedules_once
from models.content_run import ContentRunScheduleRequest, ContentRunStatus
from routes.scheduling import cancel_content_schedule, schedule_content_run


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCursor:
    def __init__(self, docs):
        self.docs = [copy.deepcopy(doc) for doc in docs]
        self.index = 0

    def sort(self, *args, **kwargs):
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
        doc = self.docs[self.index]
        self.index += 1
        return doc


class FakeCollection:
    def __init__(self, doc):
        self.doc = copy.deepcopy(doc)

    def _get(self, path):
        value = self.doc
        for part in path.split('.'):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    async def find_one(self, query):
        if self.doc.get('run_id') != query.get('run_id'):
            return None
        return copy.deepcopy(self.doc)

    async def update_one(self, query, update):
        for key, expected in query.items():
            if self._get(key) != expected:
                return UpdateResult(0)
        for key, value in update.get('$set', {}).items():
            target = self.doc
            parts = key.split('.')
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = copy.deepcopy(value)
        return UpdateResult(1)

    def find(self, query):
        return FakeCursor([self.doc])


class FakeDb:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == 'content_runs'
        return self.collection


class ConfigFactory:
    @classmethod
    def from_env(cls):
        return object()


def approved_doc():
    return {
        'run_id': 'run-1',
        'status': ContentRunStatus.APPROVED.value,
        'approval': {'approval_id': 'approval-1', 'bundle_sha256': 'bundle-1'},
        'schedule': None,
    }


def test_schedule_requires_explicit_timezone():
    with pytest.raises(ValidationError):
        ContentRunScheduleRequest(scheduled_for=datetime(2026, 8, 21, 12, 0, 0))


@pytest.mark.asyncio
async def test_approved_run_can_be_scheduled_and_cancelled(monkeypatch):
    db = FakeDb(approved_doc())
    monkeypatch.setattr(scheduling_routes, 'get_db', lambda: db)
    monkeypatch.setattr(scheduling_routes, 'LinkedInPublisherConfig', ConfigFactory)

    future = datetime.now(timezone.utc) + timedelta(hours=2)
    scheduled = await schedule_content_run('run-1', ContentRunScheduleRequest(scheduled_for=future))

    assert scheduled['status'] == ContentRunStatus.SCHEDULED.value
    assert scheduled['schedule']['status'] == 'SCHEDULED'
    assert scheduled['schedule']['approval_id'] == 'approval-1'

    cancelled = await cancel_content_schedule('run-1')
    assert cancelled['status'] == ContentRunStatus.APPROVED.value
    assert cancelled['schedule']['status'] == 'CANCELLED'
    assert cancelled['schedule']['cancelled_at'] is not None


@pytest.mark.asyncio
async def test_due_worker_uses_scheduled_publication_claim():
    due = approved_doc()
    due['status'] = ContentRunStatus.SCHEDULED.value
    due['schedule'] = {
        'status': 'SCHEDULED',
        'scheduled_for': datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    db = FakeDb(due)
    calls = []

    class FakeCoordinator:
        def __init__(self, supplied_db):
            assert supplied_db is db

        async def publish_run(self, run_id, expected_status):
            calls.append((run_id, expected_status))

    attempted = await run_due_schedules_once(db=db, coordinator_factory=FakeCoordinator)

    assert attempted == 1
    assert calls == [('run-1', ContentRunStatus.SCHEDULED)]
