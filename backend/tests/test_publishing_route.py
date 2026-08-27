import copy
from types import SimpleNamespace

import pytest
from pymongo.errors import DuplicateKeyError

from core.linkedin import (
    LinkedInPublishError,
    LinkedInPublishPhase,
    PublicationRetrySafety,
)
from core.publication import (
    PublicationConflict,
    PublicationCoordinator,
    PublicationFailed,
    PublicationReconciliationRequired,
)
from db.mongo import _ensure_indexes
from models.content_run import ContentRunStatus


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, doc):
        self.doc = copy.deepcopy(doc)
        self.indexes = []

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

    async def create_index(self, key, **kwargs):
        self.indexes.append((key, kwargs))
        return kwargs.get('name', key)

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


class DuplicateClaimCollection(FakeCollection):
    async def update_one(self, query, update):
        publication = update.get('$set', {}).get('publication')
        if isinstance(publication, dict) and publication.get('dedupe_key'):
            raise DuplicateKeyError('duplicate publication fingerprint')
        return await super().update_one(query, update)


class FakeDb:
    def __init__(self, doc, collection_cls=FakeCollection):
        self.collection = collection_cls(doc)

    def __getitem__(self, name):
        assert name == 'content_runs'
        return self.collection


class FakeConfig:
    author_urn = 'urn:li:person:123'
    api_version = '202606'
    access_token = 'secret'


def approved_doc():
    return {
        'run_id': 'run-1',
        'status': ContentRunStatus.APPROVED.value,
        'approval': {
            'approval_id': 'approval-1',
            'bundle_sha256': 'bundle-1',
            'final_content': 'approved',
            'final_content_sha256': '61a6bb5f7259e911f67d38e8431a7e4e02e1ea13b6e20f10f0e3e7e1a5f6fe57',
            'include_visual': False,
        },
        'publication': None,
    }


@pytest.mark.asyncio
async def test_publication_dedupe_index_is_installed_before_publication_workers_run():
    db = FakeDb(approved_doc())

    await _ensure_indexes(db)

    assert db.collection.indexes == [(
        'publication.dedupe_key',
        {'unique': True, 'sparse': True, 'name': 'publication_dedupe_key_unique'},
    )]


@pytest.mark.asyncio
async def test_publish_claims_approved_run_and_persists_external_evidence():
    db = FakeDb(approved_doc())

    class FakePublisher:
        def __init__(self, config):
            assert config.author_urn == 'urn:li:person:123'

        async def publish(self, approval):
            assert approval['approval_id'] == 'approval-1'
            return SimpleNamespace(post_urn='urn:li:share:900', image_urn=None)

    coordinator = PublicationCoordinator(db, publisher_factory=FakePublisher, config_factory=lambda: FakeConfig())
    updated = await coordinator.publish_run('run-1')

    assert updated['status'] == ContentRunStatus.PUBLISHED.value
    assert updated['publication']['status'] == 'PUBLISHED'
    assert updated['publication']['external_post_urn'] == 'urn:li:share:900'
    assert updated['publication']['bundle_sha256'] == 'bundle-1'
    assert updated['publication']['content_sha256'] == approved_doc()['approval']['final_content_sha256']
    assert updated['publication']['dedupe_key']
    assert updated['publication']['failure_retry_safety'] is None
    assert updated['publication']['failure_phase'] is None


@pytest.mark.asyncio
async def test_already_published_bundle_is_idempotent_and_never_calls_linkedin_again():
    doc = approved_doc()
    doc['status'] = ContentRunStatus.PUBLISHED.value
    doc['publication'] = {
        'status': 'PUBLISHED',
        'bundle_sha256': 'bundle-1',
        'external_post_urn': 'urn:li:share:900',
    }
    db = FakeDb(doc)

    class ForbiddenPublisher:
        def __init__(self, config):
            raise AssertionError('publisher must not be constructed for an already-published bundle')

    def forbidden_config():
        raise AssertionError('publication authority must not be resolved for an already-published bundle')

    coordinator = PublicationCoordinator(db, publisher_factory=ForbiddenPublisher, config_factory=forbidden_config)
    updated = await coordinator.publish_run('run-1')

    assert updated['status'] == ContentRunStatus.PUBLISHED.value
    assert updated['publication']['external_post_urn'] == 'urn:li:share:900'


@pytest.mark.asyncio
async def test_duplicate_content_fingerprint_is_blocked_before_linkedin_call():
    db = FakeDb(approved_doc(), collection_cls=DuplicateClaimCollection)

    class ForbiddenPublisher:
        def __init__(self, config):
            raise AssertionError('publisher must not be constructed when the content fingerprint is already claimed')

    coordinator = PublicationCoordinator(db, publisher_factory=ForbiddenPublisher, config_factory=lambda: FakeConfig())

    with pytest.raises(PublicationConflict, match='exact approved text'):
        await coordinator.publish_run('run-1')

    assert db.collection.doc['status'] == ContentRunStatus.APPROVED.value


@pytest.mark.asyncio
async def test_explicit_safe_publish_failure_returns_run_to_approved_for_retry():
    db = FakeDb(approved_doc())

    class FailingPublisher:
        def __init__(self, config):
            pass

        async def publish(self, approval):
            raise LinkedInPublishError(
                'provider rejected before final post creation',
                retry_safety=PublicationRetrySafety.SAFE_TO_RETRY,
                phase=LinkedInPublishPhase.LOCAL_VALIDATION,
            )

    coordinator = PublicationCoordinator(db, publisher_factory=FailingPublisher, config_factory=lambda: FakeConfig())
    with pytest.raises(PublicationFailed, match='provider rejected before final post creation'):
        await coordinator.publish_run('run-1')

    assert db.collection.doc['status'] == ContentRunStatus.APPROVED.value
    assert db.collection.doc['publication']['status'] == 'FAILED'
    assert db.collection.doc['publication']['error_message'] == 'provider rejected before final post creation'
    assert db.collection.doc['publication']['failure_retry_safety'] == 'SAFE_TO_RETRY'
    assert db.collection.doc['publication']['failure_phase'] == 'LOCAL_VALIDATION'


@pytest.mark.asyncio
async def test_ambiguous_publish_error_stays_publishing_and_requires_reconciliation():
    db = FakeDb(approved_doc())

    class AmbiguousPublisher:
        def __init__(self, config):
            pass

        async def publish(self, approval):
            raise LinkedInPublishError(
                'post outcome ambiguous',
                phase=LinkedInPublishPhase.POST_CREATE,
            )

    coordinator = PublicationCoordinator(db, publisher_factory=AmbiguousPublisher, config_factory=lambda: FakeConfig())
    with pytest.raises(PublicationReconciliationRequired, match='ambiguous'):
        await coordinator.publish_run('run-1')

    assert db.collection.doc['status'] == ContentRunStatus.PUBLISHING.value
    assert db.collection.doc['publication']['status'] == 'RECONCILIATION_REQUIRED'
    assert db.collection.doc['publication']['failure_retry_safety'] == 'RECONCILIATION_REQUIRED'
    assert db.collection.doc['publication']['failure_phase'] == 'POST_CREATE'

    with pytest.raises(PublicationReconciliationRequired, match='reconciliation'):
        await coordinator.publish_run('run-1')


@pytest.mark.asyncio
async def test_unclassified_publisher_exception_defaults_to_reconciliation():
    db = FakeDb(approved_doc())

    class UnknownPublisher:
        def __init__(self, config):
            pass

        async def publish(self, approval):
            raise RuntimeError('unexpected adapter failure')

    coordinator = PublicationCoordinator(db, publisher_factory=UnknownPublisher, config_factory=lambda: FakeConfig())
    with pytest.raises(PublicationReconciliationRequired, match='Unexpected publisher outcome'):
        await coordinator.publish_run('run-1')

    assert db.collection.doc['status'] == ContentRunStatus.PUBLISHING.value
    assert db.collection.doc['publication']['status'] == 'RECONCILIATION_REQUIRED'
    assert db.collection.doc['publication']['failure_retry_safety'] == 'RECONCILIATION_REQUIRED'
    assert db.collection.doc['publication']['failure_phase'] == 'UNKNOWN'


@pytest.mark.asyncio
async def test_publishing_state_is_never_implicitly_replayed():
    doc = approved_doc()
    doc['status'] = ContentRunStatus.PUBLISHING.value
    doc['publication'] = {'status': 'PUBLISHING', 'bundle_sha256': 'bundle-1'}
    db = FakeDb(doc)
    coordinator = PublicationCoordinator(db, config_factory=lambda: FakeConfig())

    with pytest.raises(PublicationReconciliationRequired, match='reconciliation'):
        await coordinator.publish_run('run-1')
