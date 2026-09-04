# prodAgentic

prodAgentic is a governed agentic content-production system. It plans, produces, validates, reviews, stores, schedules, publishes, and learns from content for multiple editorial identities while keeping the operator in control.

## Generations

This repository now uses explicit product generations.

- **MK0** — the existing implementation lineage: the current FastAPI/Next.js product, `ContentRun` lifecycle, Content Profiles, immutable approval bundle, durable asset ownership, LinkedIn publishing, scheduling, and release hardening.
- **MK1** — the reconciled product generation. MK1 keeps the proven safety invariants from MK0 but redesigns the product around first-class Profiles, Batches, ContentItems, GenerationRuns, Editorial Memory, Novelty, structured agent contracts, VisualSpec, governed QA, queue-based execution, capability-aware distribution, analytics, and progressive-disclosure UX.

MK0 is evidence. MK1 is the current design authority for new product work.

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

Historical MK0 documents do not override an explicit MK1 decision.

## Required reading order

A new engineer or agent should read:

1. `mk1/README.md`
2. `mk1/brainstorming/PRODUCT_THESIS.md`
3. `mk1/design/PRODUCT.md`
4. `mk1/arch/SYSTEM_ARCHITECTURE.md`
5. `mk1/arch/DOMAIN_MODEL.md`
6. `mk1/arch/INVARIANTS.md`
7. `mk1/plan/DESIGN_GRAPH.md`
8. `mk1/plan/BUILD_ENTRY_CRITERIA.md`

## Build authorization phrase

MK1 uses **“Take the hummer”** as the explicit phrase meaning that the design graph is closed enough to begin implementation. The phrase is valid only when the build-entry criteria in `mk1/plan/BUILD_ENTRY_CRITERIA.md` are satisfied.
