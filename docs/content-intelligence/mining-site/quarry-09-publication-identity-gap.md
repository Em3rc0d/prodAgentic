# Quarry 09 — Atomic Publication Identity Gap

Status: **PRE-BUILD EVIDENCE**

Branch: `feat/content-intelligence-foundation`

## Question

What is actually required to turn CI-MEM-03A's advisory exact-match evidence into a hard cross-run guarantee that the same canonical approved text is not externally published twice in the same workspace?

## OBSERVED

### Existing same-run safety

`PublicationCoordinator.publish_run()` already atomically transitions a single `ContentRun` from `APPROVED` or `SCHEDULED` to `PUBLISHING` using a conditional Mongo update bound to the immutable approval ID/bundle digest.

That protects one run from being replayed concurrently.

It does **not** coordinate two different runs that contain the same approved text.

### Manual and scheduled publication share one boundary

- The manual route calls `PublicationCoordinator(db).publish_run(run_id)`.
- The scheduler calls the same coordinator with `expected_status=SCHEDULED`.

Therefore a future cross-run identity claim can be centralized in `PublicationCoordinator`; separate manual/scheduler duplicate implementations are unnecessary and would be dangerous.

### Advisory memory cannot be the hard lock

CI-MEM-03A can read prior same-workspace `PUBLISHED_CONTENT` and expose `EXACT_DUPLICATE`, but two different approved runs can both observe no published match before either publishes.

A read-before-write check has a race and cannot prove uniqueness.

### Current publisher failure taxonomy is insufficient for safe claim release

`LinkedInPublisher` currently raises the same `LinkedInPublishError` class for materially different situations, including:

- local configuration/approval/asset validation errors before a post request,
- image initialization/upload HTTP rejection,
- post creation returning a non-201 response,
- post creation returning **201 Created but no `x-restli-id` evidence**.

The last case is explicitly ambiguous: the external post may already exist even though local evidence is incomplete.

In addition, transport exceptions from `httpx` can escape `_request()` and are caught by `PublicationCoordinator` as generic exceptions. A network timeout/disconnect around the POST may not prove whether LinkedIn accepted the request.

### Current retry behavior is too coarse for a future hard guarantee

For both `LinkedInPublishError` and unexpected exceptions, the current coordinator returns the ContentRun to `APPROVED` after a failed attempt.

This behavior is acceptable only when failure is proven safe to retry. It is unsafe as a basis for hard cross-run duplicate prevention when provider outcome is ambiguous.

### Visual publication has outbound work before post creation

A visual approval can initialize/upload an image before the final `/rest/posts` request. The text-publication identity claim therefore needs to exist before the external post-creation boundary, and failure handling must distinguish asset-only side effects from a possibly-created post.

### Historical publications have no atomic identity claim

CI-MEM-03A can project `PUBLISHED_CONTENT`, including historical/new published evidence as it is encountered, but existing published runs were not created with a dedicated publication identity claim.

Enabling a claim only for future runs would not prove uniqueness against all historical published content.

## INFERRED

### Separate coordination authority is required

The atomic publication identity claim should be a dedicated coordination collection, not a field/index inside `content_memory`.

Reason:

- `content_memory` is deliberately fail-soft/advisory;
- a hard duplicate guard must fail closed when coordination readiness is unavailable;
- claim state needs ownership and reconciliation transitions that are not memory semantics.

Proposed collection name: `publication_identity_claims`.

### Canonical key

The exact guard should key by:

```text
(workspace_id, canonicalizer_version, normalized_sha256)
```

The hash must be derived directly from immutable `approval.final_content` at publication time.

It must not trust mutable root `final_content` or advisory `memory_check` as publication authority.

### Text identity is independent of visual variant

For the exact-duplicate guarantee, the same approved text should resolve to the same claim even if the visual differs. A different image does not make reposting identical text a different text publication identity.

This is an explicit product-policy choice and should remain versioned/documented.

### Conservative states

A minimal coordination state model is likely:

- `CLAIMED` — one run owns the right to attempt publication.
- `PUBLISHED` — terminal; external evidence confirms publication.
- `RELEASED` — previous attempt is proven safe to retry/reassign.
- `RECONCILIATION_REQUIRED` — outcome may have created an external post; identity remains blocked.

Absence of a document means never claimed.

### Conservative failure classification

Before releasing a claim, the system must have evidence that the final external post was not created.

At minimum distinguish:

- `SAFE_TO_RETRY` — failure proven before a potentially accepted post-creation request, or a provider rejection whose no-side-effect semantics are explicitly supported by contract/tests.
- `RECONCILIATION_REQUIRED` — any uncertain transport/provider outcome, including 201 without post ID evidence.

Unknown must never be treated as safe.

## PROPOSED

Split CI-MEM-03B into independently certified sub-slices:

### CI-MEM-03B-01 — Publication outcome taxonomy

Introduce typed failure/outcome evidence so the coordinator can distinguish safe retry from ambiguous external outcome.

No hard duplicate claim yet.

### CI-MEM-03B-02 — Atomic claim persistence

Create `publication_identity_claims` with a unique canonical key and compare-and-set acquisition/release transitions.

No enforcement activation yet.

### CI-MEM-03B-03 — Coordinator concurrency integration

Both manual and scheduled publication acquire the same claim before provider publication.

Real Mongo concurrency tests must prove two distinct runs with the same identity produce at most one provider invocation.

### CI-MEM-03B-04 — Historical backfill/readiness activation

Build/verify terminal claims for authoritative historical `PUBLISHED` runs and define readiness.

Hard duplicate protection may be called active only after:

- claim indexes are ready,
- historical backfill is complete/verified for the enforced workspace scope,
- acquisition fails closed when claim coordination is unavailable.

## REJECTED

- `find_exact()` followed by publish as a hard guard.
- A unique index on `content_memory` as publication coordination.
- Releasing a claim after every publisher exception.
- Treating `201` without external ID as a normal failure/retry.
- Treating generic network timeout as evidence that no post exists.
- Enabling hard protection only for future runs while claiming historical coverage.
- Keying the hard claim from mutable `ContentRun.final_content`.
- Semantic/high-overlap similarity as a hard automatic publication lock in this phase.

## UNKNOWN

- Which LinkedIn HTTP error classes can be contractually classified as definitely no-post-created; current code/tests do not prove this.
- How historical published runs with incomplete approval/external evidence should be handled during backfill; must fail explicit/visible rather than silently guess.
- Production contention/latency under high concurrent publication volume; not yet measured.
- Future canonicalizer migrations and whether multiple canonicalizer versions must coexist during reindex/backfill.

## Pre-build verdict

`CI-MEM-03B`: **NOT READY FOR IMPLEMENTATION AS ONE SLICE**.

The safe path is the four certified sub-slices above. The first authorized build should be only `CI-MEM-03B-01` after its contract/test gate is written.