# CI-MEM-03A Gate — Lifecycle Memory Projection

Status: **PASS / CERTIFIED**

## Purpose

Connect the deterministic memory repository to the trusted ContentRun lifecycle so current reviewable and newly published content becomes indexable and an exact previous-publication match is inspectable.

This slice remains **advisory**. It does not yet hard-block publication.

## Why hard blocking is separate

A read-before-publish exact check has a race across two distinct runs. Hard duplicate protection requires an atomic publication identity claim and is therefore reserved for `CI-MEM-03B`.

## Authorized lifecycle behavior

### When a run reaches READY_FOR_REVIEW

1. Read the authoritative `ContentRun.final_content`.
2. Upsert `FINAL_CONTENT` memory for that run/workspace.
3. Search the same workspace for exact `PUBLISHED_CONTENT` matches using canonical identity.
4. Exclude the current run.
5. Persist a compact `memory_check` snapshot on ContentRun.

### When a human edits final content during review

Repeat the same refresh after the edit is durably stored so memory never silently points to the previous revision.

### Immediately before approval

The approval path must ensure the `memory_check.normalized_sha256` corresponds to the current final content. If not, refresh it before freezing approval.

The memory refresh itself must not alter the mutable-content optimistic concurrency timestamp used to protect approval from concurrent human edits/renders.

### After successful publication evidence is finalized

1. Upsert `PUBLISHED_CONTENT` from the immutable approval text, not mutable root draft fields.
2. Store the external post URN in the memory projection.
3. Update bounded memory-index evidence on the ContentRun.

If memory indexing fails after LinkedIn publication evidence is finalized, publication remains `PUBLISHED`; memory is marked degraded. An advisory index failure must never rewrite external publication truth.

## `memory_check` snapshot contract

Certified compact shape:

```json
{
  "status": "READY|DEGRADED",
  "outcome": "CLEAR|EXACT_DUPLICATE|DEGRADED",
  "checked_at": "UTC datetime",
  "canonicalizer_version": "v1",
  "normalized_sha256": "...",
  "final_memory_id": "...",
  "candidates": [
    {
      "memory_id": "...",
      "run_id": "...",
      "content_status": "PUBLISHED",
      "external_post_urn": "...",
      "text_preview": "..."
    }
  ],
  "error_message": null,
  "published_memory_id": null,
  "published_index_status": null,
  "published_indexed_at": null
}
```

Candidate list maximum: 3.

## Service boundary

`ContentMemoryService` is request/lifecycle-scoped.

Responsibilities:

- refresh review memory/check from an authoritative ContentRun,
- index immutable published approval content,
- convert repository failures into explicit degraded evidence when possible.

The service does not publish, approve, edit or generate content.

## Repository adjustment

`ContentMemoryRepository` accepts an optional database instance so publication and tests can use the same explicitly injected DB as their trusted lifecycle boundary. Global `get_db()` remains a backward-compatible default.

## Index initialization

Application lifespan attempts idempotent `content_memory` index creation after Mongo connects.

For CI-MEM-03A this is non-terminal to application startup; failures are logged and runtime memory checks degrade explicitly. `CI-MEM-03B` must reassess whether hard publication guard readiness should fail closed.

## Test gate

Certified:

1. READY_FOR_REVIEW refresh creates FINAL_CONTENT memory — PASS.
2. Existing same-workspace published memory yields `EXACT_DUPLICATE` — PASS.
3. Same text in another workspace is ignored — PASS.
4. Current run is excluded from its own published candidate set — PASS.
5. Human final-content edit refreshes hash/check to new revision — PASS.
6. Approval path never freezes against a stale memory hash — PASS.
7. Memory metadata refresh does not invalidate approval optimistic concurrency by touching root `updated_at` — PASS.
8. Successful publication indexes immutable approval text as PUBLISHED_CONTENT and external URN — PASS.
9. Publication remains PUBLISHED if post-success memory indexing fails — PASS.
10. Existing release lifecycle tests remain green — PASS.
11. Real Mongo restart/evidence tests remain green — PASS.
12. Frontend remains green — PASS.

## Certification evidence

Implementation head certified:

`55c77794c2956496f7e3c5e095482dba51e8ec1a`

GitHub Actions PR run:

`32865316281`

Observed:

- Backend smoke import: PASS.
- Backend compile: PASS.
- Backend pytest: **108 passed, 1 warning in 38.15s**.
- MongoDB 7.0.40 real lifecycle fixtures: PASS.
- Frontend lint/tests/build: PASS.

The certification gate also exposed and led to correction of a real compatibility issue when historical/serialized runs contain explicit `memory_check: null`; the evidence trail is preserved in `../mining-site/quarry-08-lifecycle-memory.md`.

## Non-goals

- Hard cross-run publication block.
- Atomic publication hash claim.
- Semantic similarity.
- Embeddings.
- Backfill of all historical runs.
- UI redesign.

## Exit criterion

**Satisfied.** CI-MEM-03A lifecycle projection is green and certified.

The next permitted activity is to document, challenge and test-design `CI-MEM-03B` before implementing the atomic exact-publication claim.