# CI-MEM-03B-01 Gate — Publication Outcome Taxonomy

Status: **READY FOR BUILD**

## Purpose

Make publication retry safety explicit before any atomic publication identity claim can depend on provider failure semantics.

This slice changes outcome classification only. It does **not** add `publication_identity_claims`, cross-run locking or historical backfill.

## Problem being fixed

Today `LinkedInPublishError` and generic exceptions can represent both:

- failures that certainly happened before the final external post could be created, and
- failures where LinkedIn may already have accepted/created the post.

The current coordinator generally resets either class to ordinary retry state. That is too coarse for a future no-duplicate guarantee.

## Contract

Introduce explicit retry-safety evidence:

```text
SAFE_TO_RETRY
RECONCILIATION_REQUIRED
```

Optional phase evidence should identify where failure occurred, for example:

```text
CONFIG
LOCAL_VALIDATION
IMAGE_INITIALIZE
IMAGE_UPLOAD
POST_CREATE
UNKNOWN
```

Names may vary, but semantics may not.

## Conservative default

Any unclassified/unknown publisher exception is **RECONCILIATION_REQUIRED**.

`UNKNOWN != SAFE_TO_RETRY`.

## Safe-to-retry class

A failure may be marked `SAFE_TO_RETRY` only when the implementation proves the final post-creation boundary was not reached.

Authorized safe examples in this slice:

- invalid/missing local approval text,
- invalid/missing approved visual snapshot,
- missing/changed local visual bytes,
- image initialization/upload failure before the final `/rest/posts` request,
- local configuration failure that occurs before the ContentRun publication claim.

Image-only provider side effects do not equal a published LinkedIn post; the exact text publication claim is concerned with the final post creation side effect.

## Reconciliation-required class

Must include:

- `201 Created` from `/rest/posts` without required `x-restli-id` evidence,
- transport timeout/disconnect/unknown exception around the final post request,
- any final-post provider response whose no-side-effect semantics are not explicitly proven by current provider contract/tests,
- any otherwise unclassified exception after the run entered `PUBLISHING`.

This deliberately prefers a temporary blocked/reconciliation state over a potentially duplicated external post.

## Coordinator behavior

### SAFE_TO_RETRY

After a claimed publication attempt fails safely:

```text
ContentRun -> APPROVED
publication.status -> FAILED
```

For a scheduled attempt, schedule failure evidence remains explicit and a future user retry/reschedule is required.

Raise/return ordinary `PublicationFailed` semantics.

### RECONCILIATION_REQUIRED

After an ambiguous provider outcome:

```text
ContentRun -> PUBLISHING
publication.status -> RECONCILIATION_REQUIRED
```

For scheduled attempts:

```text
schedule.status -> RECONCILIATION_REQUIRED
```

Do not reset the run to `APPROVED`.

Do not automatically retry.

Raise `PublicationReconciliationRequired` so both manual route and scheduler use their existing reconciliation handling path.

### Confirmed success

Unchanged:

```text
201 + external post id
  -> finalize local PUBLISHED evidence
```

CI-MEM-03A published-memory projection remains post-success and fail-soft.

## Backward compatibility

`LinkedInPublishError` may remain the public base exception type so existing imports/tests are not gratuitously broken, but its default retry classification must be conservative, not silently safe.

Existing successful text/visual publication behavior must remain unchanged.

## Test gate

Required before certification:

1. Missing/blank approval text fails before final post and is `SAFE_TO_RETRY`.
2. Approved visual byte mismatch is `SAFE_TO_RETRY` and performs no outbound request.
3. Image init/upload failure is `SAFE_TO_RETRY` because final post creation was not attempted.
4. Successful `201 + x-restli-id` remains confirmed success.
5. `201` without `x-restli-id` is `RECONCILIATION_REQUIRED`.
6. Final POST transport exception is `RECONCILIATION_REQUIRED`.
7. An unclassified publisher exception defaults to reconciliation, not safe retry.
8. Coordinator safe failure returns run to `APPROVED` with explicit FAILED evidence.
9. Coordinator ambiguous failure leaves run in `PUBLISHING` with `publication.status=RECONCILIATION_REQUIRED`.
10. Scheduled ambiguous failure is not picked up as ordinary retry work and carries reconciliation evidence.
11. Existing same-run replay/reconciliation tests remain green.
12. CI-MEM-03A publication-memory tests remain green.
13. Full backend suite with real Mongo remains green.
14. Frontend lint/tests/build remain green.

## Non-goals

- atomic cross-run claim,
- unique claim index,
- hard duplicate enforcement,
- historical claim backfill,
- semantic overlap,
- UI changes,
- automatic LinkedIn reconciliation/deletion.

## Exit criterion

Only after this taxonomy is CI-certified may `CI-MEM-03B-02` implement atomic claim persistence and use safe-vs-ambiguous semantics for future claim transitions.