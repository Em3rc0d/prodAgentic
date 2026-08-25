# Quarry 08 — Lifecycle Memory Projection

Verdict: **PASS**

Branch: `feat/content-intelligence-foundation`
Draft PR: #24
Certified head: `55c77794c2956496f7e3c5e095482dba51e8ec1a`
GitHub Actions PR run: `32865316281`

## Question

Can deterministic workspace-scoped content memory be connected to the trusted ContentRun lifecycle without becoming publication authority, invalidating approval concurrency, or creating a false hard-duplicate guarantee?

## OBSERVED

### Review lifecycle

- When the pipeline reaches `READY_FOR_REVIEW`, `ContentMemoryService.refresh_review()` projects authoritative `ContentRun.final_content` as `FINAL_CONTENT` memory.
- Exact candidate lookup is restricted to the same `workspace_id` and `PUBLISHED_CONTENT` records.
- Same bytes in another workspace are ignored.
- The current run is explicitly excluded from its own candidate set.
- Exact historical matches produce `memory_check.outcome = EXACT_DUPLICATE`; no match produces `CLEAR`.
- Candidate evidence is bounded to three records.

### Human edit and approval

- A human final-content edit durably updates the run/post projection first and then refreshes content memory.
- The existing `FINAL_CONTENT` memory record is updated idempotently for the same `(workspace, run, kind)` rather than multiplying records for each edit.
- Before approval, the current canonical hash is compared with `memory_check.normalized_sha256`; a stale check is refreshed before approval bytes are frozen.
- Memory refresh writes `memory_check` without modifying root `ContentRun.updated_at`, preserving the existing optimistic concurrency contract for human edits/renders.

### Publication lifecycle

- `PublicationCoordinator` still publishes only the immutable approval snapshot.
- After provider success and local `PUBLISHED` finalization, the immutable `approval.final_content` is projected as `PUBLISHED_CONTENT` together with the external post URN.
- Mutable root `final_content` is not used as publication-memory truth.
- If memory indexing fails after external/local publication success, the publication remains `PUBLISHED`; advisory memory evidence degrades instead of rolling back publication truth.
- Replaying an already-published run with the same approval bundle does not publish externally again, but can heal/backfill a missing published-memory projection.

### Startup/index behavior

- Application lifespan attempts idempotent content-memory index creation after Mongo connection.
- CI-MEM-03A keeps this startup step fail-soft; hard fail-closed behavior is intentionally deferred to the future atomic publication guard decision.

## Failure evidence preserved

The first full CI-MEM-03A lifecycle run failed with **3 failed / 105 passed**. The failures were not hidden or reclassified as flaky.

Two were test-fixture defects:

1. PyMongo returned BSON UTC datetimes without `tzinfo` under the default codec while the fixture compared them to a timezone-aware UTC value. The test now compares the same UTC instant without weakening the `updated_at` invariant.
2. One generated Mongo test database name exceeded MongoDB's 63-character database-name limit. Test database prefixes were shortened.

The third failure exposed a real compatibility bug:

- A run containing explicit `memory_check: null` could not receive `memory_check.published_*` fields through MongoDB dot notation (`Cannot create field below null parent`).
- Production code was corrected so a missing/non-object memory check receives the complete snapshot atomically before nested updates are used.
- The published projection test remained strict: expected status stayed `READY`; the test was not weakened to accept `DEGRADED`.

This is relevant to historical or model-serialized ContentRuns where optional `memory_check` may be persisted as null.

## Final CI evidence

Certified head:

`55c77794c2956496f7e3c5e095482dba51e8ec1a`

GitHub Actions run:

`32865316281`

Observed:

- MongoDB service: **MongoDB 7.0.40 healthy**.
- Backend smoke import: **PASS**.
- Backend compile: **PASS**.
- Backend pytest: **108 passed, 1 warning in 38.15s**.
- Real Mongo workspace isolation: **PASS**.
- Real Mongo self-exclusion: **PASS**.
- Real Mongo edit refresh: **PASS**.
- Real Mongo stale-memory-before-approval repair: **PASS**.
- Real Mongo immutable published projection with `memory_check: null`: **PASS**.
- Existing release Mongo restart test: **PASS** as part of the full suite.
- Frontend lint: **PASS**.
- Frontend tests: **PASS**.
- Frontend production build: **PASS**.

The one backend warning is an existing Starlette/TestClient deprecation warning and is not a CI-MEM-03A functional failure.

## INFERRED

- Deterministic lifecycle memory can remain a low-cost projection rather than becoming another authority aggregate.
- The current advisory exact-match check is useful for review evidence, but it cannot by itself guarantee cross-run publication uniqueness under concurrency.
- Preserving `updated_at` semantics avoids coupling advisory intelligence to trusted review concurrency.

## PROPOSED

Next gate: `CI-MEM-03B` should define an atomic publication-identity claim that can prevent two distinct approved runs with the same canonical identity from publishing concurrently.

That design must explicitly cover:

- workspace-scoped uniqueness,
- claim ownership,
- scheduled and manual publication through the same coordinator,
- provider failure before acceptance,
- ambiguous provider outcome / reconciliation,
- already-published identity,
- release conditions that are proven safe,
- legacy runs without a claim.

## REJECTED

- Treating the advisory read-before-publish lookup as a hard duplicate guarantee.
- Rolling back a confirmed publication because memory projection failed.
- Indexing mutable review text as published truth after approval.
- Updating root `ContentRun.updated_at` for memory-only evidence.
- Adding embeddings or semantic similarity inside this slice.

## UNKNOWN

- Correct production policy for releasing an atomic claim after all possible provider failure modes; this belongs to CI-MEM-03B design/test evidence.
- Production-scale contention/latency of a future atomic claim under many concurrent workspaces; not yet measured.
- Semantic duplicate detection quality; not implemented in CI-MEM-03A.

## Verdict

`CI-MEM-03A`: **PASS / CERTIFIED**.

The lifecycle now has deterministic advisory memory with workspace isolation and immutable publication provenance. Hard duplicate publication protection remains intentionally unclaimed until CI-MEM-03B is designed and certified.