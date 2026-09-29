from __future__ import annotations

from routes.production import _public_artifact, _public_attempts, _public_run


def _keys(value):
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(key)
            found.update(_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_keys(item))
    return found


def test_public_run_hides_internal_lineage_and_contract_metadata():
    internal = {
        "schema_version": 1,
        "run_id": "run-1",
        "content_id": "content-1",
        "profile_id": "profile-1",
        "profile_version": 1,
        "plan_id": "plan-1",
        "state": "RESEARCHING",
        "agent_run_refs": ["a1", "a2", "a3"],
        "contract_versions": ["EvidenceBundleV1@1", "structured-v1"],
        "plan_digest": "a" * 64,
        "profile_snapshot_digest": "b" * 64,
        "started_at": "2026-09-17T00:00:00Z",
    }

    public = _public_run(internal)

    assert public["run_id"] == "run-1"
    assert public["state"] == "RESEARCHING"
    assert "agent_run_refs" not in public
    assert "contract_versions" not in public
    assert "plan_digest" not in public
    assert "profile_snapshot_digest" not in public


def test_public_attempts_collapse_retries_and_hide_routing_metadata():
    attempts = [
        {
            "agent": "RESEARCH",
            "status": "FAILED",
            "safe_failure_code": "MODEL_TIMEOUT",
            "attempt": 1,
            "provider": "private-provider",
            "model": "private-model-a",
            "latency_ms": 123,
            "created_at": "2026-09-17T00:00:00Z",
        },
        {
            "agent": "RESEARCH",
            "status": "SUCCESS",
            "safe_failure_code": None,
            "attempt": 2,
            "provider": "private-provider",
            "model": "private-model-b",
            "latency_ms": 456,
            "created_at": "2026-09-17T00:00:01Z",
        },
    ]

    public = _public_attempts(attempts)

    assert public == [{
        "agent": "RESEARCH",
        "status": "SUCCESS",
        "safe_failure_code": None,
        "created_at": "2026-09-17T00:00:01Z",
    }]
    assert not ({"provider", "model", "attempt", "latency_ms"} & _keys(public))


def test_public_artifact_recursively_removes_provider_model_and_provenance():
    internal = {
        "artifact_type": "EvidenceBundleV1",
        "digest": "c" * 64,
        "payload": {
            "bundle_id": "bundle-1",
            "sources": [
                {
                    "title": "Primary source",
                    "publisher_domain": "example.com",
                    "provider": "private-provider",
                    "provenance": {
                        "model": "private-model",
                        "method": "private-grounding-method",
                        "chunk_index": 0,
                    },
                }
            ],
        },
    }

    public = _public_artifact(internal)
    keys = _keys(public)

    assert public["payload"]["sources"][0]["title"] == "Primary source"
    assert public["payload"]["sources"][0]["publisher_domain"] == "example.com"
    assert "provider" not in keys
    assert "model" not in keys
    assert "model_id" not in keys
    assert "provenance" not in keys
