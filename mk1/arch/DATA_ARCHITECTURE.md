# MK1 Data Architecture

Status: **FROZEN**

## Authority model

- **MongoDB:** system of record for domain state and durable execution evidence.
- **Redis:** transient transport/coordination.
- **AssetStore:** product-owned binary authority for rendered/imported assets.
- **ZIP/export:** derived representation, never a database.

# Mongo collections

Recommended V1 collections:

```text
tenants
profiles
profile_versions
batches
content_items
generation_runs
content_revisions
editorial_memory
assets
qa_reports
approvals
connections
schedules
publications
metric_snapshots
audit_events
job_outbox
```

Typed ResearchPack/ContentSpec/VisualSpec artifacts may initially be embedded in GenerationRun/Revision documents if document size remains controlled, or persisted in dedicated artifact collections. The architecture contract is immutability + digest/reference identity, not collection count.

# Index rules

Every business collection begins with tenant-scoped indexes.

Examples:

```text
profiles: unique (tenant_id, profile_id)
profile_versions: unique (tenant_id, profile_id, version)
batches: (tenant_id, profile_id, created_at desc)
content_items: (tenant_id, batch_id), (tenant_id, profile_id, state)
editorial_memory: (tenant_id, profile_id, effective_at desc), canonical_topic
approvals: unique (tenant_id, approval_id), (tenant_id, content_id, approved_at desc)
schedules: (tenant_id, state, scheduled_for)
publications: unique (tenant_id, idempotency_key)
metric_snapshots: (tenant_id, publication_id, captured_at desc)
job_outbox: (state, created_at), unique operation_key
```

Indexes are finalized against actual query plans during build; cross-tenant uniqueness is never assumed.

# Profile snapshots

ProfileVersion documents are immutable. Batch/Run references store identity + version + digest, and may embed a compact frozen snapshot required for model execution/audit.

# Editorial memory rebuildability

`editorial_memory` is a normalized read/index model derived from authoritative lifecycle data. A rebuild command must be possible for one Profile/Tenant without changing publication authority.

# AssetStore port

```text
put(bytes, metadata) -> storage_key + sha256
get(storage_key) -> bytes
exists(storage_key)
verify(storage_key, expected_sha256)
delete(storage_key)  # governed retention only
```

V1 adapter: durable filesystem rooted at `PRODAGENTIC_ASSET_ROOT`, preserving MK0's proven local-first contract.

Future adapters: S3/R2/MinIO compatible object stores.

Domain code never concatenates provider-specific paths directly.

# Export packages

Derived package structure:

```text
batch-<id>/
  manifest.json
  content/
    <content-id>/caption.txt
    <content-id>/metadata.json
    <content-id>/assets/...
```

Manifest contains Profile/batch identity, exact approved revision/asset hashes and platform notes. It must not contain secrets.

# Migration

MK0 `ContentRun` and `posts` remain readable during migration. New MK1 writes become authoritative per slice only after migration/backfill and regression gates are satisfied.

No destructive data migration occurs before a verified export/rollback path exists.
