# S2 Build Record — Batch + Editorial Memory + Novelty

Status: **IMPLEMENTED — CODE CANDIDATE PASSED; RECEIPT-HEAD CI REQUIRED**

Branch: `mk1/s2-batch-memory-novelty`

Started from: `main@bfa64cb7e03e2344be80a789f0871bbac2bbbcea`

## Objective

Implement the first MK1 editorial-intelligence slice without invoking the S3 production cell:

```text
Generate next batch
  -> immutable ProfileVersion
  -> Editorial Memory refresh/read
  -> oversized IdeaCandidateV1 pool
  -> explainable NoveltyEngine
  -> diversity-aware selection
  -> ContentPlanV1 artifacts
  -> first-class Batch + ContentItems
```

## Accepted authority

- `mk1/design/CREATE_FLOW.md`
- `mk1/arch/DOMAIN_MODEL.md` — Batch, ContentItem, EditorialMemoryEntry
- `mk1/arch/INVARIANTS.md` — planning/memory invariants 5–8
- `mk1/arch/EDITORIAL_ENGINE.md`
- `mk1/arch/CONTRACTS.md` — IdeaCandidateV1 + ContentPlanV1
- `mk1/arch/DATA_ARCHITECTURE.md`
- `mk1/plan/VERTICAL_SLICES.md` — S2
- `mk1/test/GOLDEN_DATASETS.md` — GD-01/02/03
- `mk1/test/ACCEPTANCE_SCENARIOS.md` — AS-02/03/11/14

No accepted contract or ADR change was required before implementation.

## Frozen implementation decisions

- Batch freezes the exact `ProfileVersion` number and digest used for planning.
- Runtime candidate target is `max(8, requested_size * 3)` with a hard V1 cap of 24.
- Novelty evaluates canonical topic, lexical/semantic overlap, angle, hook/creative pattern, visual/format pattern and current-batch collisions.
- Default cooldown policy remains `0–2 HARD`, `3–6 STRONG`, `7+ eligible only with genuinely fresh treatment`.
- `BLOCKED`, `REPLACE_TOPIC` and `REWRITE_ANGLE` candidates do not enter ContentItems.
- Same canonical topic alone is not an intra-batch veto; a genuinely different angle may pass with a warning while semantic/same-angle repetition remains blocked.
- S2 contains no PerformanceSummary input. Performance cannot override novelty because it is not consulted in this slice.
- If hard gates leave fewer ideas than requested, `selected_size < requested_size` is recorded explicitly; standards are not silently relaxed.
- ContentPlanV1 is persisted as immutable planning evidence before any later S3 GenerationRun may consume it.
- A `BatchPlanningTraceV1` persists the complete candidate/novelty/selection decision so `novelty_result_ref` is never an orphan explanation.

## Memory authority and bridge

`editorial_memory` remains a rebuildable read model, never publication authority.

S2 refreshes memory from two sources:

1. native MK1 lifecycle documents when present (`content_items` + approvals/schedules/publications);
2. the still-authoritative MK0 `content_runs` during migration, limited to `READY_FOR_REVIEW`, `APPROVED`, `SCHEDULED`, `PUBLISHING`, and `PUBLISHED`.

Legacy projection is conservative and does not pretend MK0 had the richer structured planning contract. It preserves topic/idea/status identity and normalizes only evidence that exists. Refresh replaces stable `native-` and `mk0-` projections rather than append-drifting the read model.

MongoDB BSON timestamps are UTC but Motor/PyMongo returns them as naive datetimes unless the client is configured `tz_aware`. The S2 Mongo planning adapter therefore rehydrates all nested Mongo datetimes as timezone-aware UTC when crossing back into domain models. This keeps cooldown arithmetic and reloaded `TargetWindow` evidence deterministic without leaking adapter ambiguity into the domain.

## Feature flags

- backend: `MK1_ENABLED=true` + `MK1_BATCH_PLANNING=true`;
- frontend: `NEXT_PUBLIC_MK1_SHELL=true` + `NEXT_PUBLIC_MK1_BATCH_PLANNING=true`;
- defaults remain off in runtime examples;
- CI explicitly enables S1+S2 only for certification.

## Failure paths

- feature disabled -> bounded 404;
- Profile missing/current version missing -> bounded 404/409;
- cross-tenant access -> structural rejection through scoped repositories;
- candidate source returns too few candidates -> honest partial Batch;
- all candidates collide -> Batch may select zero and records the reason;
- memory refresh failure is not converted into false freshness; request fails rather than planning statelessly;
- S3 production is not called in S2;
- ordinary persistence failure before the Batch commit marker compensates trace/plans/items and returns failure.

## Persistence and commit boundary

New tenant-scoped collections:

- `batches`
- `content_items`
- `content_plans`
- `editorial_memory`
- `planning_traces`

The write order is intentionally:

```text
planning trace
-> selected ContentPlans
-> selected ContentItems
-> Batch LAST
```

`Batch` is therefore the commit/visibility marker. An ordinary precommit error is compensated. A hard process death may leave orphan precommit evidence, but cannot leave a visible Batch pointing at missing selected evidence. Orphans remain identifiable by `tenant_id + batch_id` and can be reconciled without changing publication authority.

Indexes follow `DATA_ARCHITECTURE.md` and include tenant identity first.

## Product surface

`/create` is an S2-gated low-friction cockpit:

- Profile selector;
- Tomorrow / This week;
- 1 / 4 / 7 pieces;
- optional constraints hidden behind one disclosure;
- `Generate next batch` as the primary action;
- selected/requested count, memory/pool/blocked telemetry and concise planning evidence after completion.

The UI does not expose models, agents, thresholds or backend schema controls. Planning evidence remains progressively disclosed; tests and browser certification open the native `<details>` control before asserting its contents rather than forcing the product UI permanently open for test convenience.

## Test implementation

- `backend/tests/test_mk1_s2_planning.py` covers deterministic contracts, cooldowns, soft review memory, current-batch collision, partial completion and GD-01/02/03 planning fixtures.
- `backend/tests/test_mk1_s2_mongo.py` covers real-Mongo legacy memory rebuild, idempotent projection, frozen ProfileVersion evidence, tenant isolation, Mongo UTC hydration and the Batch-last commit boundary.
- `frontend/__tests__/mk1-batch-create.test.tsx` covers the default 4-piece request, partial truthfulness, optional constraints and explicit opening of planning evidence.
- `frontend/e2e/ui-cert.spec.ts` includes `/create` desktop/mobile frames and an S2 API+browser acceptance scenario that exercises the planning-evidence disclosure.

## Hardened implementation candidate

Exact code candidate:

```text
3aa962e0d1bd378a3fa0eaa1b252dcd0a69affa2
```

Canonical CI:

```text
workflow: CI #698
run:      33981477379
backend:  101347356016  PASS
frontend: 101347356155  PASS
browser:  101347635464  PASS
```

Browser evidence artifact:

```text
id:      9973926294
name:    ui-01-cert-evidence
sha256:  1591618c8759a7a57bf8e2523fd3979be4c2374fb4b3c7bc3f03f28dc48791bc
```

The candidate was hardened after CI exposed two concrete issues:

1. real Mongo memory hydration returned BSON UTC timestamps without tzinfo, causing aware/naive cooldown arithmetic to fail; the planning repository now restores UTC awareness recursively at the Mongo/domain boundary and regression coverage reloads both memory and nested Batch target-window timestamps;
2. frontend/browser tests asserted content inside a closed native `<details>` as visible; tests now perform the real disclosure interaction instead of weakening progressive disclosure in the product.

## Manual final review of the code candidate

Accepted on `3aa962e0d1bd378a3fa0eaa1b252dcd0a69affa2`:

- `EditorialMemoryEntry` remains a rebuildable read model and is not publication authority.
- tenant scope is structurally injected by `TenantScopedMongoRepository`; S2 indexes begin with `tenant_id`.
- Batch, selected ContentItems and persisted ContentPlans freeze the ProfileVersion used for planning.
- `PerformanceSummary` is absent from the S2 strategy snapshot/runtime input.
- S2 routes instantiate planning/profile/memory adapters only; no Research/Writer/Editor/Visual production cell and no external publishing path is invoked.
- the Batch-last commit marker continues to prevent incomplete precommit evidence from masquerading as a visible committed Batch under ordinary failures.
- progressive disclosure remains product behavior; certification exercises it rather than bypassing it.

## Required certification

- contract validation and canonical normalization;
- candidate pool strictly larger than requested when source capacity permits;
- hard and strong cooldown behavior;
- same-angle/topic, creative-hook and current-batch collision cases;
- insufficient novelty returns fewer honestly;
- ProfileVersion is frozen into Batch/ContentItem/plan evidence;
- legacy/native memory projection is rebuildable/idempotent;
- tenant isolation negative matrix;
- Content Seller / Logan / Tech golden planning fixtures;
- real-Mongo persistence + memory rebuild;
- frontend lint/Jest/build;
- desktop/mobile Create flow browser certification;
- exact-SHA evidence receipt before merge.

The code candidate satisfies these gates. The documentation receipt head created after binding this evidence must itself pass unchanged canonical CI before merge.

## Rollback

Disable S2 backend/frontend feature flags. S1 Profile V2 remains authoritative and operational. S2 collections are additive read/planning evidence and do not need destructive deletion for rollback.

## Known limitations

- S2 intentionally does not call Research/Writer/Editor/Visual; production begins in S3.
- semantic comparison is deterministic/provider-free in S2; embedding adapters remain calibratable future implementation behind the same novelty contract.
- native Approval/Schedule/Publication authority is introduced by later slices; until then the MK0 lifecycle bridge supplies migration-era memory where applicable.
- hard process death before the Batch commit marker can leave orphan planning evidence; it cannot expose a committed Batch. Reconciliation of such orphan evidence is a bounded operational cleanup concern, not editorial/publication authority.
