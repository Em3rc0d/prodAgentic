# MK1 Domain Model

Status: **FROZEN**

## Aggregate map

```text
Tenant
├── Profile ──< ProfileVersion
├── Batch ──< ContentItem ──< GenerationRun ──< ContentRevision
├── EditorialMemoryEntry
├── Asset
├── QAReport
├── Approval
├── Schedule
├── Publication
├── MetricSnapshot
├── Connection
└── AuditEvent
```

Not every persisted document is an aggregate root. Typed agent outputs such as ResearchPack and VisualSpec are immutable run/revision artifacts referenced by digest/id.

# Tenant

Represents the data-isolation root.

```text
Tenant
- tenant_id
- name
- status: ACTIVE | SUSPENDED | ARCHIVED
- created_at
- updated_at
```

Every new MK1 business record carries `tenant_id`. The server derives tenant context from authenticated identity/session; clients do not choose arbitrary tenant authority.

# Profile

Stable identity pointer.

```text
Profile
- profile_id
- tenant_id
- current_version
- name
- status: ACTIVE | ARCHIVED
- created_at
- updated_at
```

# ProfileVersion

Immutable editorial identity configuration.

```text
ProfileVersion
- profile_id
- tenant_id
- version
- identity
- goals[]
- audience[]
- editorial_strategy
- novelty_policy
- copy_policy
- claim_policy
- visual_system
- publishing_preferences
- agent_policy
- inferred_from_examples[]
- accepted_at
- created_at
- digest
```

Connections/secrets never live here.

# Batch

Represents one planned content-production request for a Profile and target window.

```text
Batch
- batch_id
- tenant_id
- profile_id
- profile_version
- target_window {start_at, end_at, timezone}
- requested_size
- selected_size
- request_constraints
- strategy_snapshot
- state
- summary_counts
- created_at
- updated_at
```

`strategy_snapshot` freezes planner-relevant context such as requested roles/formats, memory window reference, performance-summary version and planner policy version.

# ContentItem

Represents the conceptual publication within a Batch, independent of how many attempts/revisions it takes to produce it.

```text
ContentItem
- content_id
- tenant_id
- batch_id
- profile_id
- profile_version
- canonical_topic
- subtopics[]
- angle
- role
- target_effect
- format
- hook_pattern
- visual_pattern
- state
- current_revision_id
- latest_approval_id
- created_at
- updated_at
```

# GenerationRun

Represents one bounded production attempt for a ContentItem.

```text
GenerationRun
- run_id
- tenant_id
- content_id
- profile_snapshot_ref + digest
- plan_ref + digest
- state
- contract_versions
- agent_run_refs[]
- research_pack_ref
- content_spec_ref
- editorial_review_ref
- visual_spec_ref
- qa_report_refs[]
- failure
- started_at
- completed_at
```

Regeneration creates a new run. It never overwrites previous run provenance.

# ContentRevision

Represents the exact mutable/reviewable content package produced by a run or human edit fork.

```text
ContentRevision
- revision_id
- tenant_id
- content_id
- parent_revision_id?
- source: GENERATION | HUMAN_EDIT | REWRITE | VISUAL_REGEN
- content_spec_ref + digest
- visual_spec_ref + digest?
- asset_refs[]
- qa_report_id
- status: DRAFT | QA_PENDING | REVIEWABLE | SUPERSEDED
- created_at
```

Approval refers to one exact revision. Editing an approved result creates a new revision; it does not mutate the approved one.

# EditorialMemoryEntry

Normalized representation of an audience-consumed or imminently committed editorial concept.

```text
EditorialMemoryEntry
- memory_id
- tenant_id
- profile_id
- content_id
- revision_id
- lifecycle_source
- canonical_topic
- subtopics[]
- angle
- hook_pattern
- role
- format
- visual_pattern
- entities[]
- semantic_fingerprint
- embedding_ref?
- effective_at
- cooldown_until?
- weight
- created_at
```

Memory can be derived/rebuilt from authoritative content data; it is a query/read model plus indexed semantics, not publication authority.

# Asset

Product-owned bytes and metadata.

```text
Asset
- asset_id
- tenant_id
- owner_revision_id
- kind
- storage_key
- mime_type
- size_bytes
- sha256
- width?
- height?
- page_index?
- renderer
- render_id
- created_at
```

# QAReport

```text
QAReport
- qa_report_id
- tenant_id
- revision_id
- policy_version
- deterministic_checks[]
- semantic_checks[]
- visual_checks[]
- warnings[]
- failures[]
- verdict: PASS | PASS_WITH_WARNINGS | FAIL
- created_at
- digest
```

# Approval

First-class immutable human authority.

```text
Approval
- approval_id
- tenant_id
- content_id
- revision_id
- profile_snapshot_digest
- plan_digest
- research_digest
- content_digest
- visual_spec_digest?
- assets[{asset_id, sha256}]
- qa_report_digest
- policy_version
- approved_by
- approved_at
- bundle_sha256
```

# Connection

External account/credential relationship.

```text
Connection
- connection_id
- tenant_id
- provider
- external_identity
- encrypted_secret_ref/token material
- capability_snapshot
- status
- created_at
- updated_at
```

Secrets are encrypted and never copied into Profile/Approval/agent prompts.

# Schedule

```text
Schedule
- schedule_id
- tenant_id
- approval_id
- connection_id? / manual target
- provider
- scheduled_for
- timezone_context
- state
- job_key
- created_at
- cancelled_at?
- completed_at?
```

Schedule never copies mutable content.

# Publication

```text
Publication
- publication_id
- tenant_id
- approval_id
- schedule_id?
- provider
- connection_id
- state
- idempotency_key
- attempt_id
- bundle_sha256
- external_post_id?
- external_asset_ids[]
- started_at
- completed_at?
- safe_error?
- reconciliation_reason?
- receipt_digest?
```

# MetricSnapshot

```text
MetricSnapshot
- metric_snapshot_id
- tenant_id
- publication_id
- provider
- captured_at
- raw_available_metrics
- normalized_metrics
- freshness
- source_version
```

Snapshots are append-only observations, not overwritten counters.

# AuditEvent

```text
AuditEvent
- event_id
- tenant_id
- event_type
- entity_type
- entity_id
- actor_type
- actor_id?
- correlation ids
- safe_metadata
- created_at
```

Audit events contain no secrets or full sensitive prompt payloads by default.
