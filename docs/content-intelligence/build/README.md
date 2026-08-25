# Build Plan — Content Intelligence

Status: ACTIVE / GATED INCREMENTAL BUILD

## Build philosophy

Construction proceeds in small independently testable slices. No slice may weaken the trusted release lifecycle.

Each slice follows:

```text
contract -> model -> persistence -> service -> route/orchestrator integration -> tests -> quarry evidence -> certification
```

If a slice cannot be proven without requiring the next slice, it is too large and must be split.

Current rule:

```text
UNKNOWN != PASS
ADVISORY != HARD GUARANTEE
CI GREEN != FEATURE CLAIM UNLESS THE FEATURE GATE ITSELF IS COVERED
```

---

# Phase 0 — Foundation / isolation

## CI-FND-01 Workspace scope — CERTIFIED

Implemented:
- server-resolved `APP_WORKSPACE_ID`,
- backward-compatible `legacy-default`,
- workspace identity on new ContentRuns/intelligence records,
- workspace-scoped intelligence queries,
- client does not become workspace authority.

Important boundary:
- this is an isolation foundation, not a claim of production multi-tenant auth/workspace ownership.

---

# Phase 1 — CI-01 Content Memory

## CI-MEM-01 Canonical duplicate identity — CERTIFIED

Implemented deterministic versioned text canonicalization + SHA-256.

`v1` normalizes:
- Unicode NFKC,
- case,
- whitespace.

Punctuation remains significant in v1.

## CI-MEM-02 Memory persistence — CERTIFIED

Implemented `content_memory` as an inspectable workspace-scoped projection.

Current kinds:
- `FINAL_CONTENT`,
- `PUBLISHED_CONTENT`.

Certified properties:
- unique `(workspace_id, run_id, kind)`,
- idempotent update,
- exact lookup by canonical identity,
- bounded preview,
- real MongoDB index/isolation evidence.

## CI-MEM-03A Advisory lifecycle projection — CERTIFIED

The old build-plan idea of a single "exact overlap blocking check" was split after proving that read-before-publish cannot close a race across distinct runs.

Implemented advisory behavior:
- index `FINAL_CONTENT` at `READY_FOR_REVIEW`,
- exact same-workspace lookup against published memory,
- bounded `memory_check` evidence,
- refresh after human final-content edits,
- refresh stale memory before approval,
- preserve root `updated_at` concurrency semantics,
- index immutable approved text as `PUBLISHED_CONTENT` after confirmed publication,
- fail-soft memory projection after publication,
- idempotent published replay may heal missing memory without republishing.

This slice intentionally does **not** claim hard cross-run duplicate prevention.

See:
- `CI-MEM-03A-GATE.md`,
- `../mining-site/quarry-08-lifecycle-memory.md`,
- `../../changes/PR-CI-MEM-03A.md`.

## CI-MEM-03B Atomic exact publication protection — DESIGNED AS FOUR SLICES

See `CI-MEM-03B-GATE.md` and `../mining-site/quarry-09-publication-identity-gap.md`.

### CI-MEM-03B-01 Publication outcome taxonomy — NEXT

Purpose:
- distinguish `SAFE_TO_RETRY` from `RECONCILIATION_REQUIRED` before a future identity claim depends on failure semantics.

No atomic claim/enforcement in this sub-slice.

### CI-MEM-03B-02 Atomic claim persistence — BLOCKED BY 03B-01

Add dedicated `publication_identity_claims` coordination persistence with unique:

```text
(workspace_id, canonicalizer_version, normalized_sha256)
```

The claim is coordination authority, not content memory.

### CI-MEM-03B-03 PublicationCoordinator concurrency integration — BLOCKED

Manual + scheduled publication must acquire the same identity claim at their shared `PublicationCoordinator` boundary.

Real Mongo concurrency must prove at most one provider invocation across distinct runs with identical exact identity.

### CI-MEM-03B-04 Historical backfill + readiness activation — BLOCKED

Hard protection is not advertised READY until authoritative historical published content is backfilled/verified and claim coordination can fail closed.

## CI-MEM-04 Embedding provider abstraction — BLOCKED UNTIL EXACT GUARD PROGRAM IS STABLE

Interface target:

```text
embed(text) -> model/version/vector
```

Provider is centrally configured and must degrade explicitly.

## CI-MEM-05 Semantic similarity — BLOCKED

Use embeddings only after exact-memory/publication contracts are stable.

Result must distinguish:
- `NO_OVERLAP`,
- `RELATED`,
- `HIGH_OVERLAP`,
- `UNKNOWN/DEGRADED`.

Semantic overlap remains advisory; it must not silently rewrite approved content or become a hard automatic publication lock in this phase.

## CI-MEM-06/07 evidence UI — DEFERRED UNTIL BACKEND CONTRACTS STABILIZE

The run already persists bounded `memory_check` evidence. UI exposure remains intentionally later to avoid polishing unstable backend semantics.

---

# Phase 2 — CI-02 Source Grounding

Status: DOCUMENTED / NOT YET BUILT

## CI-SRC-01 Source model/repository

Add `content_sources` with workspace + run scope, digest, authority, type and bounded snapshot.

## CI-SRC-02 Source attach API

Initial source input supports pasted text/user assertion first.

Connector-based sources remain adapters; do not build GitHub/Drive crawlers in this slice.

## CI-SRC-03 Grounding snapshot on ContentRun

Store mode, selected source IDs and source-set digest.

## CI-SRC-04 Research pipeline integration

Resolve bounded sources before ResearchAgent invocation.

Mode rules:
- OPEN: normal pipeline with optional source context,
- SOURCE_PREFERRED: prioritize source facts,
- SOURCE_ONLY: prohibit unsupported specificity and return insufficiency warning when necessary.

## CI-SRC-05 Approval binding

Freeze grounding mode + source-set digest in approval snapshot.

## CI-SRC-06 Review UI

Display attached sources + mode + digest identity compactly.

---

# Phase 3 — CI-03 Visual Intelligence

Status: DOCUMENTED / NOT YET BUILT

## CI-VIS-01 VisualIntent model

Create typed intent classes and snapshot.

## CI-VIS-02 VisualIntentService

Single request-scoped classification/generation step based on final content + profile.

## CI-VIS-03 VisualAgent integration

Change current visual prompt generation from:

```text
post only -> prompt
```

to:

```text
post + VisualIntent -> prompt
```

## CI-VIS-04 Persistence

Persist intent snapshot before/with visual prompt generation.

## CI-VIS-05 Review UI

Show intent class, communication goal, required/avoid elements.

## CI-VIS-06 Fallback

Visual-intent failure remains non-terminal. Existing renderer/digest/approval contracts remain untouched.

---

# Phase 4 — Integration hardening

## CI-INT-01 Approval non-regression

Prove content intelligence cannot alter approved text/visual bytes.

## CI-INT-02 Schedule non-regression

Scheduled publication still uses only immutable approval bundle.

## CI-INT-03 Exact publication guard

This requirement is now owned by CI-MEM-03B rather than a naïve memory lookup.

## CI-INT-04 Reconciliation

Existing `PUBLISHING` safety must be strengthened, not weakened, by the outcome taxonomy + atomic identity claim.

---

# Phase 5 — UI polishing

Only after backend contracts are proven:
- creation: optional source attach,
- run review: related content + sources + visual intent,
- Content Library: minimal evidence badges/signals,
- no separate Brain page,
- no onboarding questionnaire.

---

# Deferred build backlog

Not part of the current exact-memory sequence:
- Voice analysis from historical posts,
- Opportunity Mining,
- claim-level evidence graph beyond bounded coordination needs,
- analytics feedback loop,
- campaign graph,
- multi-social publishing.

---

# Commit discipline

Keep commits/slices independently reviewable and certified. No giant mixed commit.

Current next build authorization:

```text
CI-MEM-03B-01 publication outcome taxonomy ONLY
```

No claim collection, source grounding, embeddings or visual-intelligence build should enter until that gate is written and green.