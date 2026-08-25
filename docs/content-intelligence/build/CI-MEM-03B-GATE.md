# CI-MEM-03B Gate — Atomic Exact Publication Protection

Status: **DESIGN / NOT YET AUTHORIZED AS A SINGLE BUILD**

## Purpose

Turn exact canonical publication identity into a hard same-workspace coordination guarantee across distinct ContentRuns without weakening the existing immutable approval and reconciliation contracts.

This program is intentionally split because a unique hash lock without provider-outcome semantics and historical readiness would create a false safety claim.

## Guaranteed scope when complete

The completed CI-MEM-03B program may claim only:

> For a workspace whose publication-identity guard is READY, two distinct ContentRuns with the same `canonicalizer_version + normalized_sha256` derived from immutable approved text cannot both pass the prodAgentic publication coordinator as new external publication attempts.

It does **not** guarantee semantic/paraphrase uniqueness.

## Authority boundaries

### Authoritative publication text

Always:

```text
approval.final_content
```

Never:

```text
ContentRun.final_content
memory_check
content_memory.text_preview
embedding result
```

### Coordination authority

A dedicated `publication_identity_claims` collection is authorized for CI-MEM-03B.

`content_memory` remains advisory/evidence only.

## Canonical claim key

```text
workspace_id
canonicalizer_version
normalized_sha256
```

Unique index required across all three fields.

Text identity is intentionally independent of visual variation for this exact duplicate guard.

## Proposed claim contract

Bounded shape:

```json
{
  "claim_id": "uuid",
  "workspace_id": "...",
  "canonicalizer_version": "v1",
  "normalized_sha256": "...",
  "state": "CLAIMED|PUBLISHED|RELEASED|RECONCILIATION_REQUIRED",
  "claim_generation": 1,
  "owner_run_id": "...",
  "approval_id": "...",
  "bundle_sha256": "...",
  "publication_attempt_id": "...",
  "claimed_at": "UTC",
  "resolved_at": null,
  "external_post_urn": null,
  "last_failure_class": null,
  "last_failure_message": null
}
```

The exact implementation may adjust naming, but not weaken the state/ownership evidence.

## State semantics

### CLAIMED

One run/approval owns the exact identity for an active publication attempt.

Another run with the same key must not call the external publisher.

### PUBLISHED

Terminal exact-publication evidence exists. Future distinct runs with the same key are blocked.

### RELEASED

The previous attempt is proven safe to retry because the post-creation side effect is known not to have occurred.

A new owner may acquire only through atomic compare-and-set from `RELEASED` to `CLAIMED` and must increment claim generation.

### RECONCILIATION_REQUIRED

External outcome is ambiguous or local finalization lost certainty after a potentially accepted request.

The identity remains blocked until an explicit reconciliation mechanism resolves it. No automatic release.

## Program slices

# CI-MEM-03B-01 — Publication outcome taxonomy

Status before build: **NEXT GATE**

### Purpose

Make retry safety explicit before any hard claim can depend on it.

### Required behavior

The publication layer must distinguish at least:

- `SAFE_TO_RETRY`
- `RECONCILIATION_REQUIRED`

The classification must preserve phase/context so evidence can show whether the final post-creation boundary was reached.

### Conservative rule

`UNKNOWN != SAFE_TO_RETRY`.

A 201 response without the required external post ID is reconciliation-required.

Transport/network uncertainty around the final post request is reconciliation-required unless a stronger provider contract proves otherwise.

Local/config/approval/asset validation that occurs before any final post request is safe to retry.

### Required tests

1. Missing/invalid local publisher config is safe before publication attempt.
2. Invalid approved content/visual bytes that stop before outbound post creation are safe.
3. Successful `201 + x-restli-id` yields confirmed published evidence.
4. `201` without `x-restli-id` is reconciliation-required.
5. Transport exception around final POST is not converted to safe retry.
6. Coordinator does not return an ambiguous outcome to ordinary `APPROVED` retry semantics.
7. Existing successful text and visual publisher tests remain green.
8. Existing publication/reconciliation tests remain green.

### Exit criterion

No claim persistence may depend on failure release semantics until this slice is green.

---

# CI-MEM-03B-02 — Atomic claim persistence

Status: BLOCKED BY 03B-01

### Purpose

Provide workspace-scoped atomic coordination independent of provider calls.

### Required persistence behavior

- unique `(workspace_id, canonicalizer_version, normalized_sha256)` index,
- acquire missing identity atomically,
- `RELEASED -> CLAIMED` compare-and-set transition,
- distinct owner cannot acquire `CLAIMED`, `PUBLISHED`, or `RECONCILIATION_REQUIRED`,
- same-owner retries obey explicit state rules rather than bypassing state,
- every acquisition binds run + approval + bundle + publication attempt,
- no arbitrary client-supplied workspace scope.

### Required tests

1. Two concurrent inserts for same key: exactly one owner wins.
2. Different workspaces may independently claim same text.
3. PUBLISHED is terminal.
4. RECONCILIATION_REQUIRED blocks acquisition.
5. RELEASED can be reacquired by one contender only.
6. Claim generation increments on reacquire.
7. Real MongoDB 7 unique/CAS behavior is proven.
8. Claim repository unavailable returns explicit not-ready/fail-closed result when enforcement is requested.

---

# CI-MEM-03B-03 — PublicationCoordinator integration

Status: BLOCKED BY 03B-01 + 03B-02

### Purpose

Put the claim at the one boundary shared by manual and scheduled publication.

### Required ordering

Conceptually:

```text
load ContentRun
  -> verify immutable approval
  -> derive canonical identity from approval.final_content
  -> create publication attempt identity
  -> atomically acquire exact publication claim
  -> claim same-run ContentRun PUBLISHING state
  -> external publisher
  -> classify result
      -> confirmed success: finalize ContentRun + claim PUBLISHED
      -> safe retry failure: return ContentRun safely + claim RELEASED
      -> ambiguous: preserve reconciliation state + claim RECONCILIATION_REQUIRED
```

The exact ordering between claim acquisition and same-run `PUBLISHING` CAS must be implemented so a loser cannot leave durable orphan state and a crash has a deterministic reconciliation path.

### Required concurrency tests

1. Two distinct APPROVED runs, same workspace/text, concurrent manual attempts -> at most one publisher invocation.
2. Manual run racing a different scheduled run with same identity -> at most one publisher invocation.
3. Two scheduled workers/runs with same identity -> at most one publisher invocation.
4. Same text in different workspaces -> both may publish independently.
5. Winner success -> claim PUBLISHED with external URN.
6. Safe pre-post failure -> claim RELEASED and explicit retry can reacquire.
7. 201-without-ID -> claim RECONCILIATION_REQUIRED and no automatic second publisher invocation.
8. Network ambiguity -> claim RECONCILIATION_REQUIRED.
9. Existing same-run idempotent publication remains green.
10. Existing scheduler cancellation/claim behavior remains green.

Real MongoDB must be used for the cross-run race gate.

---

# CI-MEM-03B-04 — Historical backfill + guard readiness

Status: BLOCKED BY 03B-03

### Purpose

Prevent rollout from claiming more coverage than actually exists.

### Required behavior

Before hard enforcement is advertised READY for a workspace:

1. identify authoritative historical `PUBLISHED` ContentRuns,
2. require sufficient immutable approval/publication evidence to derive claim identity,
3. seed/verify terminal PUBLISHED claims idempotently,
4. report incomplete/unreconcilable historical rows explicitly,
5. create/verify required unique indexes,
6. mark guard readiness only after backfill verification succeeds,
7. fail closed at publication if enforcement is enabled but claim coordination/readiness is unavailable.

No silent guessing from text previews or incomplete memory records.

### Required tests

1. Historical published run with complete evidence seeds PUBLISHED claim.
2. Backfill is idempotent across reruns/restarts.
3. Duplicate historical identities are surfaced as migration evidence, not silently overwritten.
4. Historical row missing authority evidence produces explicit unresolved result.
5. Guard cannot report READY while unresolved backfill remains under enforced scope.
6. New publication fails closed when guard is configured/enforced but claim store/index readiness is unavailable.
7. Application can remain in a documented advisory/not-ready mode before enforcement activation without falsely claiming hard protection.
8. Real Mongo restart preserves claim/backfill evidence.

## Activation rule

Only CI-MEM-03B-04 completion may change product wording/state from:

```text
Exact duplicate advisory evidence
```

to:

```text
Exact duplicate publication guard READY
```

for the verified workspace scope.

## Non-goals

- semantic/paraphrase hard blocking,
- automatic rewriting of duplicate content,
- vector DB requirement,
- per-user agents,
- multi-social coordination,
- provider-side deletion/reconciliation automation without evidence,
- changing immutable approval bytes,
- trusting UI state as coordination authority.

## Current verdict

CI-MEM-03B overall: **DESIGNED AS A PROGRAM, NOT YET CERTIFIED**.

Next authorized implementation slice after documentation review: **CI-MEM-03B-01 only**.