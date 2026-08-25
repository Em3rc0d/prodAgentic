# Build Plan — Content Intelligence

Status: PLANNED, NOT YET IMPLEMENTED

## Build philosophy

Construction proceeds in small independently testable slices. No slice may weaken the trusted release lifecycle.

Each slice follows:

```text
contract -> model -> persistence -> service -> route/orchestrator integration -> UI signal -> tests -> quarry evidence
```

If a slice cannot be proven without requiring the next slice, it is too large and must be split.

---

# Phase 0 — Foundation / isolation

## CI-FND-01 Workspace scope

Purpose:
- prevent future semantic/source lookups from becoming cross-tenant by accident.

Changes:
- introduce a resolved `workspace_id` concept with backward-compatible default legacy workspace,
- add optional/required workspace identity to new intelligence records,
- add workspace identity to new ContentRuns created on this branch without breaking legacy reads,
- centralize workspace resolution rather than trusting arbitrary client-supplied IDs.

Do not claim multi-tenant production support until auth-to-workspace ownership is explicitly mapped.

Acceptance:
- all new intelligence repository queries require workspace scope,
- tests prove records in workspace A cannot appear in workspace B queries,
- legacy single-workspace flows remain green.

---

# Phase 1 — CI-01 Content Memory

## CI-MEM-01 Canonical duplicate identity

Implement deterministic text canonicalization + SHA-256.

Targets:
- idea,
- final content,
- published approved content.

Acceptance:
- whitespace/case-only variants produce same canonical hash according to canonicalizer contract,
- materially different content produces different hash,
- canonicalizer is versioned.

## CI-MEM-02 Memory persistence

Add `content_memory` repository/collection.

Persist bounded metadata and optional embedding.

Acceptance:
- one unique record per `(workspace_id, run_id, kind)`,
- update is idempotent,
- no raw secrets,
- publication evidence can be linked after publish.

## CI-MEM-03 Exact overlap check

Before approval/publication, check normalized final content against published memory in same workspace.

Acceptance:
- exact/normalized duplicate returns a blocking result,
- other workspace ignored,
- provider independence: works without embeddings.

## CI-MEM-04 Embedding provider abstraction

Interface only first:

```text
embed(text) -> model/version/vector
```

Provider is configured centrally.

Acceptance:
- unavailable provider returns explicit degraded state,
- no unbounded retries,
- no generation failure because semantic memory is unavailable.

## CI-MEM-05 Semantic similarity

Use stored embeddings when available.

Acceptance:
- top candidates are workspace-scoped,
- thresholds are configuration + golden-dataset calibrated,
- result distinguishes `NO_OVERLAP`, `RELATED`, `HIGH_OVERLAP`, `UNKNOWN/DEGRADED`.

## CI-MEM-06 ContentRun evidence

Persist bounded `memory_check` snapshot on the run.

The snapshot records:
- check ID/time,
- query representation kind,
- provider/model when applicable,
- exact duplicate flag,
- top candidates + scores,
- outcome,
- degraded reason.

## CI-MEM-07 Review UI

Add a compact `Related content` panel in run detail.

No dashboard expansion in initial slice.

---

# Phase 2 — CI-02 Source Grounding

## CI-SRC-01 Source model/repository

Add `content_sources` collection with workspace + run scope, digest, authority, type and bounded snapshot.

## CI-SRC-02 Source attach API

Initial source input supports pasted text/user assertion first.

Connector-based sources remain adapters; do not build GitHub/Drive connectors in this slice.

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

Do not mutate an existing approval if sources later change.

## CI-SRC-06 Review UI

Display attached sources + mode + digest identity compactly.

---

# Phase 3 — CI-03 Visual Intelligence

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

Persist intent snapshot on ContentRun before/with visual prompt generation.

## CI-VIS-05 Review UI

Show intent class, communication goal, required/avoid elements.

## CI-VIS-06 Fallback

Visual intent failure remains non-terminal. Existing renderer and digest/approval contracts remain untouched.

---

# Phase 4 — Integration hardening

## CI-INT-01 Approval non-regression

Prove content intelligence cannot alter approved text/visual bytes.

## CI-INT-02 Schedule non-regression

Scheduled publication still uses only immutable approval bundle.

## CI-INT-03 Publish duplicate gate

Before creating a new external post, exact duplicate protection checks workspace published memory in addition to existing same-run idempotency.

Important: semantic high-overlap warnings must not create unsafe automatic rewrites at the publication boundary.

## CI-INT-04 Reconciliation

Existing `PUBLISHING` reconciliation safety remains unchanged.

---

# Phase 5 — UI polishing

Only after backend contracts are proven:

- creation: optional source attach, no mandatory setup,
- run review: related content + sources + visual intent,
- Content Library: minimal badges/signals,
- no separate Brain page,
- no onboarding questionnaire.

---

# Deferred build backlog

Not part of this branch's first implementation sequence:

- Voice analysis from historical posts,
- Opportunity Mining,
- claim-level evidence graph,
- analytics feedback loop,
- campaign graph,
- multi-social publishing.

---

# Commit discipline

Recommended commits:

1. `docs: define content intelligence contracts`
2. `feat(scope): add workspace-scoped intelligence foundation`
3. `feat(memory): add canonical content memory`
4. `feat(memory): add semantic overlap service`
5. `feat(sources): add grounded content run sources`
6. `feat(visual): add visual intent layer`
7. `test: certify content intelligence lifecycle`
8. `docs: record quarry evidence and release verdict`

No giant mixed commit.