import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import core.publication as publication_core
import routes.scheduling as scheduling_routes
from core.linkedin_oauth import LinkedInOAuthError
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


def approved_doc():
    return {
        'run_id': 'run-1',
        'status': ContentRunStatus.APPROVED.value,
        'approval': {'approval_id': 'approval-1', 'bundle_sha256': 'bundle-1'},
        'schedule': None,
    }


def configure_oauth_only(monkeypatch):
    class OAuthOnlyService:
        def __init__(self, db):
            self.db = db

        async def publisher_config(self):
            return SimpleNamespace(author_urn='urn:li:person:oauth-member')

    monkeypatch.setattr(publication_core, 'LinkedInOAuthService', OAuthOnlyService)
    monkeypatch.setenv('LINKEDIN_STATIC_FALLBACK_ENABLED', 'false')
    monkeypatch.delenv('LINKEDIN_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('LINKEDIN_AUTHOR_URN', raising=False)


def test_schedule_requires_explicit_timezone():
    with pytest.raises(ValidationError):
        ContentRunScheduleRequest(scheduled_for=datetime(2026, 8, 21, 12, 0, 0))


@pytest.mark.asyncio
async def test_oauth_only_approved_run_can_be_scheduled_and_cancelled(monkeypatch):
    db = FakeDb(approved_doc())
    monkeypatch.setattr(scheduling_routes, 'get_db', lambda: db)
    configure_oauth_only(monkeypatch)

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
async def test_schedule_fails_closed_when_publication_authority_is_unavailable(monkeypatch):
    db = FakeDb(approved_doc())
    monkeypatch.setattr(scheduling_routes, 'get_db', lambda: db)
    monkeypatch.setenv('LINKEDIN_STATIC_FALLBACK_ENABLED', 'false')
    monkeypatch.delenv('LINKEDIN_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('LINKEDIN_AUTHOR_URN', raising=False)

    class MissingOAuthService:
        def __init__(self, supplied_db):
            assert supplied_db is db

        async def publisher_config(self):
            raise LinkedInOAuthError('LinkedIn member is not connected')

    monkeypatch.setattr(publication_core, 'LinkedInOAuthService', MissingOAuthService)

    future = datetime.now(timezone.utc) + timedelta(hours=2)
    with pytest.raises(HTTPException) as exc_info:
        await schedule_content_run('run-1', ContentRunScheduleRequest(scheduled_for=future))

    assert exc_info.value.status_code == 503
    assert 'not connected' in str(exc_info.value.detail)
    assert db.collection.doc['status'] == ContentRunStatus.APPROVED.value
    assert db.collection.doc['schedule'] is None


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
