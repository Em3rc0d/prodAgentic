# PR-CI-MEM-03A — Advisory Lifecycle Memory

Status: IMPLEMENTED / CI GREEN / CERTIFIED
Branch: `feat/content-intelligence-foundation`
Draft PR: #24

## Intent

Connect deterministic workspace-scoped content memory to the existing trusted review, approval and publication lifecycle without changing publication authority or pretending advisory lookup is an atomic duplicate guard.

## Implemented

- Request-scoped `ContentMemoryService`.
- Automatic `FINAL_CONTENT` projection when a run reaches `READY_FOR_REVIEW`.
- Exact same-workspace lookup against prior `PUBLISHED_CONTENT` only.
- Current-run self-exclusion and bounded duplicate candidates.
- Compact `ContentRun.memory_check` evidence.
- Memory refresh after human final-content edits.
- Pre-approval stale-hash detection and refresh.
- Memory-only refresh preserves root `ContentRun.updated_at`.
- `PUBLISHED_CONTENT` projection from immutable `approval.final_content` after publication finalization.
- External LinkedIn post URN retained in published memory.
- Post-success memory failures are fail-soft and never roll back `PUBLISHED` truth.
- Already-published idempotent replay can repair missing memory without externally republishing.
- Lifespan attempts idempotent memory-index initialization.
- Compatibility handling for runs persisted with `memory_check: null`.

## Authority rule

`ContentRun` + immutable approval + publication evidence remain authoritative.

`content_memory` and `memory_check` remain inspectable projections only.

CI-MEM-03A does **not** claim cross-run atomic duplicate prevention.

## CI evidence

Certified implementation head:

`55c77794c2956496f7e3c5e095482dba51e8ec1a`

GitHub Actions PR run:

`32865316281`

Observed:

- Backend smoke import: PASS.
- Backend compile: PASS.
- Backend pytest: **108 passed, 1 warning in 38.15s**.
- MongoDB 7.0.40 real lifecycle fixtures: PASS.
- Existing release/Mongo restart coverage: PASS.
- Frontend lint/tests/build: PASS.

## Gate value demonstrated

The pre-certification run exposed three failures. Two were corrected test-fixture issues; one exposed a real Mongo compatibility defect for `memory_check: null`. The production implementation was fixed while the published-memory expectation remained strict.

See `docs/content-intelligence/mining-site/quarry-08-lifecycle-memory.md` for the full evidence trail.

## Not implemented

- atomic cross-run publication identity claim,
- hard duplicate publication blocking,
- semantic similarity,
- embeddings/vector retrieval,
- historical mass backfill,
- source grounding,
- visual-intent intelligence.

## Verdict

`CI-MEM-03A`: **PASS / CERTIFIED**.

Next authorized activity: document and challenge the `CI-MEM-03B` atomic publication-claim design before writing its implementation.