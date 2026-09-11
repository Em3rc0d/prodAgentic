"""Focused regressions through the real BSON codec, without a Mongo daemon."""
from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace
from bson import BSON
import pytest
from application.profiles import ProfileService, DeterministicProfileAnalyzer
from application.quality.policy import build_qa_report
from domain.profiles.models import canonical_digest
from domain.approval.models import ApprovalBundleV2, canonical_approval_sha256
from domain.tenants.models import TenantContext
from infrastructure.mongo.profiles import MongoProfileRepository
from infrastructure.mongo.quality import MongoQualityRepository
from infrastructure.mongo.approval import MongoApprovalRepository
from tests.test_mk1_s1_profiles import setup_payload

NOW = datetime(2026, 9, 11, 12, 0, 0, 123456, tzinfo=timezone.utc)
CONTEXT = TenantContext('tenant-local', 'operator-local')

class BsonCollection:
    def __init__(self):
        self.documents = []
    async def insert_one(self, document):
        self.documents.append(BSON.encode(document).decode())
    async def find_one(self, criteria):
        return next((dict(d) for d in self.documents if all(d.get(k) == v for k, v in criteria.items())), None)
    async def update_one(self, criteria, update):
        for document in self.documents:
            if all(document.get(k) == v for k, v in criteria.items()):
                document.update(BSON.encode(update['$set']).decode())
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

@pytest.mark.asyncio
async def test_profile_create_and_append_preserve_exact_frozen_digest(monkeypatch):
    monkeypatch.setattr('application.profiles.service.utc_now', lambda: NOW)
    db = defaultdict(BsonCollection)
    repo = MongoProfileRepository(db, CONTEXT)
    service = ProfileService(repo, DeterministicProfileAnalyzer())
    setup = setup_payload()
    accepted = await service.create(CONTEXT.tenant_id, setup, service.propose(setup).proposal_digest)
    stored = await repo.get_version(accepted.profile.profile_id, 1)
    assert stored == accepted.version
    assert canonical_digest(stored) == accepted.version.digest
    updated_setup = setup_payload(name='Updated profile')
    updated = await service.update(CONTEXT.tenant_id, accepted.profile.profile_id, 1, updated_setup, service.propose(updated_setup).proposal_digest)
    assert updated.version.accepted_at == NOW
    assert canonical_digest(updated.version) == updated.version.digest

@pytest.mark.asyncio
async def test_qa_report_roundtrip_preserves_hash_and_detects_tampering():
    db = defaultdict(BsonCollection)
    repo = MongoQualityRepository(db, CONTEXT)
    report = build_qa_report(qa_report_id='qa-local', tenant_id=CONTEXT.tenant_id, revision_id='revision-local', content_spec_digest='a'*64, render_input_digest=None, asset_digests=(), deterministic_checks=(), semantic_checks=(), visual_checks=(), created_at=NOW)
    await repo.save_report(report)
    assert await repo.get_report(CONTEXT.tenant_id, report.qa_report_id) == report
    db['qa_reports'].documents[0]['created_at'] = NOW.replace(microsecond=0).isoformat()
    with pytest.raises(ValueError):
        await repo.get_report(CONTEXT.tenant_id, report.qa_report_id)

@pytest.mark.asyncio
async def test_approval_bundle_roundtrip_preserves_exact_export_authority():
    db = defaultdict(BsonCollection)
    repo = MongoApprovalRepository(db, CONTEXT)
    payload = dict(schema_version=2, approval_id='approval-local', tenant_id=CONTEXT.tenant_id, content_id='content-local', revision_id='revision-local', profile_snapshot_digest='a'*64, plan_digest='b'*64, research_digest='c'*64, content_digest='d'*64, visual_spec_digest=None, assets=(), qa_digest='e'*64, policy_version='s7-v1', approved_by=CONTEXT.actor_id, approved_at=NOW)
    bundle = ApprovalBundleV2(**payload, bundle_sha256=canonical_approval_sha256(payload))
    await repo.save_bundle(bundle)
    assert await repo.get_bundle(CONTEXT.tenant_id, bundle.approval_id) == bundle
    await repo.save_bundle(bundle)
    assert len(db['approval_bundles'].documents) == 1
    db['approval_bundles'].documents[0]['approved_at'] = NOW.replace(microsecond=0).isoformat()
    with pytest.raises(ValueError):
        await repo.get_bundle(CONTEXT.tenant_id, bundle.approval_id)

def test_qa_order_is_chronological_across_legacy_bson_and_exact_iso_rows():
    from infrastructure.mongo.quality import _report_order
    old = {'created_at': NOW.replace(microsecond=0, tzinfo=None), 'qa_report_id': 'old'}
    new = {'created_at': NOW.isoformat(), 'qa_report_id': 'new'}
    assert max([old, new], key=_report_order) is new
