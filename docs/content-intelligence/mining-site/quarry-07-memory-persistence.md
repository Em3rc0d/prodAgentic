# Quarry 07 — Deterministic Memory Persistence Evidence

Date: 2026-08-25 UTC
Branch: `feat/content-intelligence-foundation`
Draft PR: #24
Certified head: `e3fca2bb08783b8b1bc403c6b96af981dd2b7f40`
CI run: `32806251822`

## Scope

This quarry certifies `CI-MEM-02` only:

- deterministic content-memory data model,
- workspace-scoped Mongo persistence,
- idempotent upsert,
- exact normalized lookup,
- indexes and preview bounds.

It does NOT certify lifecycle integration, publication blocking, or semantic similarity.

## OBSERVED — implementation

New files:

- `backend/models/content_memory.py`
- `backend/db/content_memory.py`
- `backend/tests/test_content_memory.py`

### Record contract

Supported kinds:

- `FINAL_CONTENT`
- `PUBLISHED_CONTENT`

Persisted fields include:

- `memory_id`
- `workspace_id`
- `run_id`
- `kind`
- canonicalizer version
- normalized SHA-256
- bounded text preview
- content status
- optional external post URN
- created/updated timestamps

### Workspace invariant

Repository operations reject missing/blank workspace scope before querying Mongo.

Exact lookup always includes `workspace_id`.

No global fallback exists.

### Idempotent upsert

Identity:

`(workspace_id, run_id, kind)`

Repeated upsert of the same representation retains one record and the same `memory_id`.

Changing content for the same run/kind updates the canonical hash while retaining the record identity and original creation time.

### Preview boundary

`text_preview` is capped at 500 Unicode characters and is explicitly non-authoritative for publication.

## OBSERVED — MongoDB index evidence

CI used a real MongoDB 7 service.

The Mongo logs show successful creation of:

### Unique projection identity

`uq_content_memory_workspace_run_kind`

Keys:

```text
workspace_id: 1
run_id: 1
kind: 1
```

Unique: true.

### Exact lookup index

`ix_content_memory_exact_lookup`

Keys:

```text
workspace_id: 1
normalized_sha256: 1
content_status: 1
```

## OBSERVED — test results

GitHub Actions backend:

- smoke import: PASS
- compileall: PASS
- pytest: **102 passed, 1 warning in 37.64s**

The warning is the same pre-existing Starlette/httpx test-client deprecation warning.

Frontend:

- npm install: PASS
- lint: PASS
- tests: PASS
- production build: PASS

## OBSERVED — isolation behavior

The real-Mongo test persisted identical published text in `workspace-a` and `workspace-b`.

Lookup in workspace A returned only A.
Lookup in workspace B returned only B.

Status filtering also prevented a `PUBLISHED` record from appearing in an `APPROVED` query.

## INFERRED

The deterministic memory projection is now safe enough to integrate into lifecycle events without introducing semantic-provider dependencies.

## Important concurrency finding before publication integration

A read-before-publish check alone cannot guarantee cross-run duplicate prevention.

Race example:

```text
Run A exact-check -> no published duplicate
Run B exact-check -> no published duplicate
Run A external publish
Run B external publish
```

Therefore a future hard publication block requires an **atomic publication identity claim**, not only `find_exact()`.

This is a design requirement discovered before implementing the guard.

## NOT YET PROVEN

- Automatic FINAL_CONTENT memory creation at review readiness.
- Automatic PUBLISHED_CONTENT memory creation after successful publication.
- Durable run-level `memory_check` snapshot.
- Historical backfill.
- Atomic cross-run publication claim.
- Semantic similarity.

## Verdict

### CI-MEM-02

**PASS — DETERMINISTIC MEMORY PERSISTENCE GREEN**

Next safe slice:

`CI-MEM-03A` — lifecycle projection + inspectable exact-memory check, with no hard publication block yet.

Hard duplicate publication blocking is reserved for `CI-MEM-03B` after an atomic claim contract is documented and tested.