# PR-CI-MEM-02 — Deterministic Content Memory Persistence

Status: IMPLEMENTED / CI GREEN
Branch: `feat/content-intelligence-foundation`
Draft PR: #24

## Intent

Persist exact content identity as a workspace-scoped, inspectable projection without introducing embeddings or changing publication authority.

## Implemented

- `ContentMemoryKind` with `FINAL_CONTENT` and `PUBLISHED_CONTENT`.
- `ContentMemoryRecord` validation.
- `ContentMemoryRepository.ensure_indexes()`.
- Workspace-mandatory `upsert()`.
- Workspace-mandatory `find_exact()`.
- 500-character bounded preview.
- Versioned deterministic content hash from CI-MEM-01.
- Unique `(workspace_id, run_id, kind)` index.
- Exact `(workspace_id, normalized_sha256, content_status)` lookup index.

## Authority rule

`content_memory` is an index/evidence projection only.

It must never replace:

- ContentRun final content,
- immutable approval content,
- visual artifact bytes,
- publication evidence.

## CI evidence

Head:

`e3fca2bb08783b8b1bc403c6b96af981dd2b7f40`

GitHub Actions run:

`32806251822`

Observed:

- Backend smoke import: PASS.
- Backend compile: PASS.
- Backend pytest: **102 passed, 1 warning in 37.64s**.
- Real MongoDB 7 index creation: PASS.
- Real MongoDB workspace isolation fixture: PASS.
- Frontend lint/tests/build: PASS.

See `docs/content-intelligence/mining-site/quarry-07-memory-persistence.md`.

## Important design result

A simple exact lookup is not sufficient for a hard cross-run publication guarantee because two identical runs can pass a read-before-write check concurrently.

Therefore this change does not pretend to block publication yet.

## Not implemented

- lifecycle auto-indexing,
- `memory_check` on ContentRun,
- hard duplicate publication guard,
- publication hash claim,
- embeddings/vector search,
- semantic overlap.

## Verdict

`CI-MEM-02`: PASS.

Next: `CI-MEM-03A` lifecycle projection/check only. Atomic publication blocking follows separately as `CI-MEM-03B`.