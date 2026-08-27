# CI-MEM-02 Gate — Deterministic Content Memory Persistence

Status: READY FOR BUILD

## Why this slice exists

`CI-MEM-01` proved a deterministic canonical identity. That identity has no durable cross-run value until it is persisted in a workspace-scoped memory boundary.

This slice deliberately stops before semantic embeddings.

## Authorized capability

Persist and retrieve deterministic memory records for durable content representations.

Initial kinds:

- `FINAL_CONTENT`
- `PUBLISHED_CONTENT`

`IDEA` is deferred until exact product behavior around idea-level blocking/warnings is needed.

## Data contract

Collection: `content_memory`

Record:

```json
{
  "memory_id": "uuid",
  "workspace_id": "workspace",
  "run_id": "run",
  "kind": "FINAL_CONTENT|PUBLISHED_CONTENT",
  "canonicalizer_version": "v1",
  "normalized_sha256": "64 hex chars",
  "text_preview": "bounded preview",
  "content_status": "READY_FOR_REVIEW|APPROVED|PUBLISHED",
  "external_post_urn": null,
  "created_at": "UTC datetime",
  "updated_at": "UTC datetime"
}
```

No embeddings/vector fields are required in this slice.

## Persistence invariants

1. Every repository operation requires an explicit `workspace_id`.
2. Upsert identity is `(workspace_id, run_id, kind)`.
3. Upsert is idempotent for the same representation.
4. A changed representation updates hash/preview/status and `updated_at`; original `created_at` remains stable.
5. Exact duplicate lookup requires both `workspace_id` and `normalized_sha256`.
6. No lookup may fall back to global scope.
7. `text_preview` is bounded and is not the publication authority.
8. Full final content remains authoritative on `ContentRun`/approval; memory is an index/evidence projection.

## Preview contract

Initial maximum: 500 Unicode characters.

The preview exists only to make a duplicate result inspectable. It must never be used as the source text for publication.

## Index contract

At minimum:

- unique compound index `(workspace_id, run_id, kind)`
- exact lookup index `(workspace_id, normalized_sha256, content_status)`

Index creation must be idempotent.

## Initial integration boundary

This slice implements repository/model behavior and tests only.

It does **not yet** automatically write memory from every lifecycle event and does **not yet** block publication.

That separation allows us to prove storage and isolation first.

## Test gate

Required before CI-MEM-02 PASS:

- create memory record,
- repeat same upsert without duplicate record,
- update same run/kind with changed content,
- exact lookup returns same-workspace record,
- identical hash in another workspace is invisible,
- missing/blank workspace rejected,
- preview bounded to 500 chars,
- canonicalizer version persisted,
- Mongo-backed integration path green,
- full existing backend suite green,
- frontend remains green despite no UI change.

## Explicit non-goals

- semantic similarity,
- embeddings,
- approximate duplicate detection,
- publication blocking,
- automatic backfill,
- cross-workspace search,
- UI badges.

## Exit criterion

Only after these persistence/isolation tests are green may `CI-MEM-03` integrate exact duplicate checks into lifecycle boundaries.