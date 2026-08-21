import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.publishing as publishing_routes
from core.linkedin import LinkedInPublishError
from models.content_run import ContentRunStatus
from routes.publishing import publish_content_run


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


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
            actual = self._get(key)
            if actual != expected:
                return UpdateResult(0)
        for key, value in update.get('$set', {}).items():
            target = self.doc
            parts = key.split('.')
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = copy.deepcopy(value)
        return UpdateResult(1)


class FakeDb:
    def __init__(self, doc):
        self.collection = FakeCollection(doc)

    def __getitem__(self, name):
        assert name == 'content_runs'
        return self.collection


class FakeConfig:
    author_urn = 'urn:li:person:123'
    api_version = '202606'
    access_token = 'secret'


class FakeConfigFactory:
    @classmethod
    def from_env(cls):
        return FakeConfig()


def approved_doc():
    return {
        'run_id': 'run-1',
        'status': ContentRunStatus.APPROVED.value,
        'approval': {
            'approval_id': 'approval-1',
            'bundle_sha256': 'bundle-1',
            'final_content': 'approved',
            'include_visual': False,
        },
        'publication': None,
    }


@pytest.mark.asyncio
async def test_publish_claims_approved_run_and_persists_external_evidence(monkeypatch):
    db = FakeDb(approved_doc())
    monkeypatch.setattr(publishing_routes, 'get_db', lambda: db)
    monkeypatch.setattr(publishing_routes, 'LinkedInPublisherConfig', FakeConfigFactory)

    class FakePublisher:
        def __init__(self, config):
            assert config.author_urn == 'urn:li:person:123'

        async def publish(self, approval):
            assert approval['approval_id'] == 'approval-1'
            return SimpleNamespace(post_urn='urn:li:share:900', image_urn=None)

    monkeypatch.setattr(publishing_routes, 'LinkedInPublisher', FakePublisher)

    updated = await publish_content_run('run-1')

    assert updated['status'] == ContentRunStatus.PUBLISHED.value
    assert updated['publication']['status'] == 'PUBLISHED'
    assert updated['publication']['external_post_urn'] == 'urn:li:share:900'
    assert updated['publication']['bundle_sha256'] == 'bundle-1'


@pytest.mark.asyncio
async def test_publish_failure_returns_run_to_approved_for_explicit_retry(monkeypatch):
    db = FakeDb(approved_doc())
    monkeypatch.setattr(publishing_routes, 'get_db', lambda: db)
    monkeypatch.setattr(publishing_routes, 'LinkedInPublisherConfig', FakeConfigFactory)

    class FailingPublisher:
        def __init__(self, config):
            pass

        async def publish(self, approval):
            raise LinkedInPublishError('provider rejected request')

    monkeypatch.setattr(publishing_routes, 'LinkedInPublisher', FailingPublisher)

    with pytest.raises(HTTPException) as exc:
        await publish_content_run('run-1')

    assert exc.value.status_code == 502
    assert db.collection.doc['status'] == ContentRunStatus.APPROVED.value
    assert db.collection.doc['publication']['status'] == 'FAILED'
    assert db.collection.doc['publication']['error_message'] == 'provider rejected request'


@pytest.mark.asyncio
async def test_publishing_state_is_never_implicitly_replayed(monkeypatch):
    doc = approved_doc()
    doc['status'] = ContentRunStatus.PUBLISHING.value
    doc['publication'] = {'status': 'PUBLISHING', 'bundle_sha256': 'bundle-1'}
    db = FakeDb(doc)
    monkeypatch.setattr(publishing_routes, 'get_db', lambda: db)

    with pytest.raises(HTTPException) as exc:
        await publish_content_run('run-1')

    assert exc.value.status_code == 409
    assert 'reconciliation' in exc.value.detail
