# prodAgentic

prodAgentic is a governed agentic content-production system. It plans, produces, validates, reviews, stores, schedules, publishes, and learns from content for multiple editorial identities while keeping the operator in control.

## Current product state

The active product generation is **MK1**.

Certified implementation/product-code baseline through S2:

```text
002177e90431d6009498a88cc6eb20efc46e14b3
```

Certified/merged slices:

```text
S0 — Foundation + Bootstrap Tenant       ✅
S1 — Profile V2                         ✅
S2 — Batch + Editorial Memory + Novelty ✅
```

Post-merge canonical CI on that exact product SHA:

```text
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
run                 33982022917
```

`main` may contain later documentation-only descendants. Those do not replace the product-code certification boundary above; `mk1/STATUS.md` is the canonical ledger.

The next operator gate is **local S0→S2 acceptance** before expanding the product further.

Start here:

- [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md) — local toolchain, environment, Mongo, backend and frontend startup.
- [`mk1/test/LOCAL_ACCEPTANCE.md`](mk1/test/LOCAL_ACCEPTANCE.md) — fail-closed operator acceptance checklist.
- [`mk1/STATUS.md`](mk1/STATUS.md) — canonical certification/status ledger.

The local S0→S2 pass must not trigger the future S3 production cell or publish externally.

## Generations

This repository uses explicit product generations.

- **MK0** — the existing implementation lineage: FastAPI/Next.js product, `ContentRun` lifecycle, Content Profiles, immutable approval bundle, durable asset ownership, LinkedIn publishing, scheduling, and release hardening.
- **MK1** — the reconciled product generation. MK1 keeps proven safety invariants from MK0 but redesigns the product around first-class Profiles, Batches, ContentItems, GenerationRuns, Editorial Memory, Novelty, structured agent contracts, VisualSpec, governed QA, queue-based execution, capability-aware distribution, analytics, and progressive-disclosure UX.

MK0 is evidence and migration authority where explicitly retained. MK1 is the current design and implementation authority for new product work.

## Implemented MK1 journey today

The currently certified product path is:

```text
Bootstrap Tenant
    ↓
MK1 Shell
    ↓
Profile V2 quick setup
    ↓
proposal review
    ↓
explicit human acceptance
    ↓
immutable ProfileVersion
    ↓
Create cockpit
    ↓
Batch planning
    ↓
Editorial Memory
    ↓
Novelty + diversity
    ↓
ContentPlanV1
    ↓
Batch + ContentItems
```

Later MK1 architecture includes Research, Writer, Editor, Visual, QA, approval, scheduling, publication and learning, but those nodes must be implemented and certified by their own slices before they are treated as current MK1 authority.

## MK1 repository method

Every MK generation is organized using the same lifecycle vocabulary:

```text
brainstorming/  exploration and hypotheses; never authoritative by itself
design/         product, UX and visual design contracts
arch/           domain, application and infrastructure architecture
plan/           dependency graph, delivery order, risks and gates
build/          implementation guidance, migration notes and build records
test/           test strategy, golden datasets and certification evidence
mining-site/    evidence intake, provenance ledger and repository findings
quarries/       scoped investigations that may promote findings upstream
```

The canonical MK1 index is [`mk1/README.md`](mk1/README.md).

## Documentation authority

When documents conflict, use this precedence inside the active MK:

```text
accepted ADR / invariant
        >
arch contract
        >
design contract
        >
plan
        >
build note
        >
brainstorming / quarry finding
```

Certification receipts and `mk1/STATUS.md` establish whether an implementation slice actually crossed its required gates. Historical MK0 documents do not override an explicit MK1 decision.

## Required reading order

A new engineer or agent should read:

1. `mk1/README.md`
2. `mk1/STATUS.md`
3. `mk1/brainstorming/PRODUCT_THESIS.md`
4. `mk1/design/PRODUCT.md`
5. `mk1/arch/SYSTEM_ARCHITECTURE.md`
6. `mk1/arch/DOMAIN_MODEL.md`
7. `mk1/arch/INVARIANTS.md`
8. `mk1/plan/DESIGN_GRAPH.md`
9. `mk1/plan/BUILD_ENTRY_CRITERIA.md`
10. `docs/LOCAL_DEVELOPMENT.md` when running the product locally.

## Build authorization phrase

MK1 uses **“Take the hummer”** as the explicit phrase meaning that the design graph is closed enough to begin implementation. The phrase is valid only when the build-entry criteria in `mk1/plan/BUILD_ENTRY_CRITERIA.md` are satisfied.

Each implementation slice still requires its own exact-SHA tests, evidence and certification; the phrase never bypasses those gates.
