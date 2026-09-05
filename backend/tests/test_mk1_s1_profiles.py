from copy import deepcopy

import pytest

from application.profiles import DeterministicProfileAnalyzer, ProfileConflict, ProfileService
from application.profiles.service import ProposalMismatch
from application.profiles.legacy_bridge import adapt_legacy_profile, migrate_legacy_profiles
from domain.profiles.models import ProfileSetup, canonical_digest


def setup_payload(**overrides):
    payload = {
        "name": "Systems Field Notes",
        "account_type": "education",
        "goals": ["educate", "build_authority"],
        "audience": "software engineers learning distributed systems",
        "voice": ["Technical", "Direct"],
        "batch_size": 4,
        "channels": ["linkedin", "manual_export"],
        "examples": [
            {"kind": "caption", "label": "sample", "text": "3 ideas for reliable queues. What would you test first? #distributedSystems"},
            {"kind": "bio", "text": "I explain systems with evidence and practical diagrams."},
        ],
    }
    payload.update(overrides)
    return ProfileSetup.model_validate(payload)


class MemoryRepository:
    def __init__(self):
        self.profiles = {}
        self.versions = {}

    async def list_profiles(self):
        return list(self.profiles.values())

    async def get_profile(self, profile_id):
        return self.profiles.get(profile_id)

    async def get_version(self, profile_id, version):
        return self.versions.get((profile_id, version))

    async def create(self, profile, version):
        self.profiles[profile.profile_id] = profile
        self.versions[(profile.profile_id, version.version)] = version

    async def append_version(self, profile, version, expected_version):
        existing = self.profiles.get(profile.profile_id)
        if existing is None or existing.current_version != expected_version:
            return False
        self.versions[(profile.profile_id, version.version)] = version
        self.profiles[profile.profile_id] = profile
        return True


class BridgeCursor:
    def __init__(self, documents):
        self._documents = [deepcopy(item) for item in documents]
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._documents):
            raise StopAsyncIteration
        item = self._documents[self._index]
        self._index += 1
        return item


class BridgeUpdateResult:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class BridgeCollection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(item) for item in (documents or [])]

    @staticmethod
    def matches(document, query):
        return all(document.get(key) == value for key, value in query.items())

    def find(self, query):
        return BridgeCursor([item for item in self.documents if self.matches(item, query)])

    async def find_one(self, query):
        return next((deepcopy(item) for item in self.documents if self.matches(item, query)), None)

    async def update_one(self, query, update, upsert=False):
        existing = next((item for item in self.documents if self.matches(item, query)), None)
        if existing is not None:
            return BridgeUpdateResult()
        assert upsert and set(update) == {"$setOnInsert"}
        self.documents.append(deepcopy(update["$setOnInsert"]))
        return BridgeUpdateResult(upserted_id=str(len(self.documents)))


class BridgeDb:
    def __init__(self, legacy):
        self.collections = {
            "content_profiles": BridgeCollection(legacy),
            "profiles": BridgeCollection(),
            "profile_versions": BridgeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_inference_is_deterministic_evidenced_and_does_not_echo_raw_examples():
    analyzer = DeterministicProfileAnalyzer()
    setup = setup_payload()
    first = analyzer.propose(setup)
    second = analyzer.propose(setup)

    assert first.proposal_digest == second.proposal_digest
    assert first.setup_digest == second.setup_digest
    changed = setup.model_copy(update={"batch_size": 7})
    assert analyzer.propose(changed).proposal_digest != first.proposal_digest
    assert first.confidence == "medium"
    assert first.caption_length_tendency == "short"
    assert "question" in first.hook_tendencies
    assert "distributedsystems" in first.topic_families
    serialized = first.model_dump_json()
    assert "reliable queues" not in serialized
    assert all(len(item.sha256) == 64 for item in first.evidence)


@pytest.mark.asyncio
async def test_acceptance_creates_profile_and_immutable_version_without_secrets():
    repository = MemoryRepository()
    service = ProfileService(repository, DeterministicProfileAnalyzer())
    setup = setup_payload()
    proposal = service.propose(setup)

    accepted = await service.create("tenant-a", setup, proposal.proposal_digest)

    assert accepted.profile.current_version == 1
    assert accepted.version.version == 1
    assert accepted.version.tenant_id == "tenant-a"
    assert len(accepted.version.digest) == 64
    assert canonical_digest(accepted.version) == accepted.version.digest
    snapshot = accepted.version.model_dump_json().lower()
    assert "oauth" not in snapshot
    assert "token" not in snapshot
    with pytest.raises(Exception):
        accepted.version.copy_policy.voice_traits = ("changed",)


@pytest.mark.asyncio
async def test_update_appends_version_and_preserves_historical_snapshot():
    repository = MemoryRepository()
    service = ProfileService(repository, DeterministicProfileAnalyzer())
    original_setup = setup_payload()
    original_proposal = service.propose(original_setup)
    created = await service.create("tenant-a", original_setup, original_proposal.proposal_digest)
    old_snapshot = deepcopy(created.version.model_dump(mode="json"))

    updated_setup = setup_payload(name="Systems Lab", voice=["simple", "direct"], examples=[])
    updated_proposal = service.propose(updated_setup)
    updated = await service.update(
        "tenant-a", created.profile.profile_id, 1, updated_setup, updated_proposal.proposal_digest,
    )

    assert updated.profile.current_version == 2
    assert updated.version.copy_policy.voice_traits == ("simple", "direct")
    assert repository.versions[(created.profile.profile_id, 1)].model_dump(mode="json") == old_snapshot

    with pytest.raises(ProfileConflict):
        await service.update(
            "tenant-a", created.profile.profile_id, 1, updated_setup, updated_proposal.proposal_digest,
        )


@pytest.mark.asyncio
async def test_acceptance_rejects_changed_or_unreviewed_proposal():
    service = ProfileService(MemoryRepository(), DeterministicProfileAnalyzer())
    setup = setup_payload()
    with pytest.raises(ProposalMismatch):
        await service.create("tenant-a", setup, "0" * 64)


def test_profile_setup_rejects_schema_fields_and_requires_user_facing_choices():
    with pytest.raises(Exception):
        ProfileSetup.model_validate({**setup_payload().model_dump(), "oauth_token": "secret"})
    with pytest.raises(Exception):
        setup_payload(goals=[])


def test_legacy_bridge_is_allowlisted_versioned_and_secret_free():
    profile, version = adapt_legacy_profile({
        "tenant_id": "tenant-a",
        "profile_id": "legacy-1",
        "version": 7,
        "name": "Legacy voice",
        "audience": ["builders"],
        "voice": ["direct"],
        "core_topics": ["systems"],
        "oauth_token": "must-not-cross",
        "linkedin_secret": "must-not-cross",
    }, "tenant-a")

    assert profile.current_version == 7
    assert version.version == 7
    assert version.provenance.source == "MK0_CONTENT_PROFILE"
    serialized = version.model_dump_json().lower()
    assert "must-not-cross" not in serialized
    assert "oauth" not in serialized
    assert "secret" not in serialized


def test_legacy_bridge_rejects_cross_tenant_and_malformed_identity():
    with pytest.raises(ValueError):
        adapt_legacy_profile({"tenant_id": "tenant-b", "profile_id": "p", "name": "x"}, "tenant-a")
    with pytest.raises(ValueError):
        adapt_legacy_profile({"tenant_id": "tenant-a", "profile_id": "", "name": "x"}, "tenant-a")


@pytest.mark.asyncio
async def test_legacy_bridge_migration_is_idempotent_and_reports_invalid_rows():
    db = BridgeDb([
        {"tenant_id": "tenant-a", "profile_id": "p1", "version": 2, "name": "Valid"},
        {"tenant_id": "tenant-a", "profile_id": "", "version": 1, "name": "Invalid"},
        {"tenant_id": "tenant-b", "profile_id": "other", "version": 1, "name": "Other"},
    ])
    first = await migrate_legacy_profiles(db, "tenant-a")
    second = await migrate_legacy_profiles(db, "tenant-a")

    assert first.scanned == 2 and first.migrated == 1 and first.invalid == 1
    assert second.scanned == 2 and second.existing == 1 and second.invalid == 1
    assert not first.verified and not second.verified
    assert len(db["profiles"].documents) == 1
    assert len(db["profile_versions"].documents) == 1


@pytest.mark.asyncio
async def test_legacy_bridge_fails_closed_on_existing_profile_id_collision():
    db = BridgeDb([
        {"tenant_id": "tenant-a", "profile_id": "p1", "version": 2, "name": "Legacy"},
    ])
    db["profiles"].documents.append({
        "tenant_id": "tenant-a",
        "profile_id": "p1",
        "current_version": 1,
        "name": "Native S1 profile",
    })

    report = await migrate_legacy_profiles(db, "tenant-a")

    assert report.scanned == 1 and report.invalid == 1 and not report.verified
    assert db["profile_versions"].documents == []
    assert db["profiles"].documents[0]["name"] == "Native S1 profile"
