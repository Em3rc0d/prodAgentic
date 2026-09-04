# MK1 Build Entry Criteria — “Take the hummer” Gate

Status: **PENDING FINAL REPOSITORY REVIEW**

The phrase **“Take the hummer”** means: begin MK1 implementation according to the frozen design and vertical-slice plan.

It is not a motivational phrase; it is a gate result.

## Required conditions

### Product/UX

- [x] Product thesis and V1/non-goals explicit.
- [x] User navigation and journeys closed.
- [x] Profile Setup avoids schema-form UX.
- [x] Create, Review, Calendar and Analytics interaction contracts closed.
- [x] Signature design system defines tokens, components, states, responsive, motion and accessibility.

### Domain

- [x] Tenant/Profile/Batch/ContentItem/GenerationRun/ContentRevision/Approval/Schedule/Publication responsibilities separated.
- [x] State machines defined.
- [x] Hard invariants defined.
- [x] MK0 reuse/replacement map defined.

### Editorial/agents

- [x] Editorial Memory eligibility/dimensions defined.
- [x] Novelty layers and cooldown policy defined.
- [x] Batch candidate/selection strategy defined.
- [x] Planner vs four-agent production cell defined.
- [x] Structured contract family defined.
- [x] Retry/recovery taxonomy bounded.

### Visual/QA

- [x] VisualSpecV1 boundary defined.
- [x] RendererPort and first adapter chosen.
- [x] Asset ownership/hash rule defined.
- [x] Deterministic/semantic/visual QA defined.
- [x] Invalidation DAG defined.
- [x] Human immutable approval defined.

### Data/execution/platform

- [x] Mongo authority and collections defined.
- [x] Redis Streams transport + Mongo outbox defined.
- [x] Worker idempotency/claim/DLQ semantics defined.
- [x] Capability-aware publishing defined.
- [x] Publication uncertainty/reconciliation defined.
- [x] Manual fallback defined.
- [x] Analytics snapshots and learning boundary defined.

### Security/operations

- [x] Tenant isolation rule defined.
- [x] secret boundary defined.
- [x] untrusted research/asset boundaries defined.
- [x] observability/correlation requirements defined.

### Delivery/testing

- [x] Vertical slices defined.
- [x] Risk register exists.
- [x] Test pyramid and golden datasets defined.
- [x] End-to-end acceptance scenarios defined.
- [x] Certification evidence model defined.
- [ ] Final repository consistency review completed with no blocking contradiction.
- [ ] Design branch merged to main / accepted as canonical MK1 baseline.

## Gate rule

Only the last two unchecked conditions remain after documentation creation. Once the final self-review finds no blocking contradiction and the design baseline is accepted/merged, update this file to `Status: PASSED` and record the commit SHA in `mk1/STATUS.md`.

Non-blocking quarries do not invalidate this gate because their interfaces and policy boundaries are already closed.
