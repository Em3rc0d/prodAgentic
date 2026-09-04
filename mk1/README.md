# prodAgentic MK1

**Generation:** MK1  
**Design cycle opened:** 2026-09-04  
**Purpose:** reconcile prodAgentic into a production-grade, user-controlled, multi-profile agentic content operating system.

## Product contract

> prodAgentic is a governed agentic system for planning, producing, validating, approving, storing, scheduling, publishing, and learning from content for multiple editorial identities while keeping operational complexity inside the product rather than transferring it to the user.

The desired user experience is intentionally much smaller than the internal process:

```text
USER
Generate tomorrow -> Review -> Approve -> Schedule

SYSTEM
Profile -> Memory -> Batch planning -> Candidate pool -> Novelty -> Diversity
-> Research -> Writer -> Editor -> VisualSpec -> Render -> QA -> Human decision
-> Immutable approval -> Scheduling -> Queue -> Publication -> Receipt -> Analytics -> Memory
```

## MK1 folder contract

| Folder | Purpose | Can define authority? |
|---|---|---|
| `brainstorming/` | product exploration, assumptions, rejected alternatives | No |
| `design/` | product/UX/visual contracts | Yes, below accepted ADRs and architecture invariants |
| `arch/` | domain, agent, data, execution and platform architecture | Yes |
| `plan/` | dependency graph, slices, risks, entry/exit gates | Execution authority, not domain authority |
| `build/` | implementation mapping and migration records | Must conform to design/arch |
| `test/` | certification model and evidence requirements | Verification authority |
| `mining-site/` | observed evidence and provenance | Evidence, not policy |
| `quarries/` | bounded research questions and calibrations | No until promoted |

## Provenance labels

MK1 documentation may label assertions as:

- `OFFICIAL` — externally authoritative source or product contract explicitly accepted for MK1.
- `OBSERVED` — directly observed in current repository behavior/code.
- `INFERRED` — derived from evidence but not directly asserted by a source.
- `INSPIRED` — design influence, not a requirement to copy.
- `GENERATED` — new MK1 design choice created in this cycle.

A generated design decision becomes authoritative only when it is placed in `design/`, `arch/`, or an accepted ADR and its dependencies are closed.

## MK1 non-negotiables

1. The user is the driver; agents are the pit crew.
2. Complexity is hidden by default but observable on demand.
3. Memory precedes generation.
4. Batches are planned before pieces are produced.
5. Agents exchange structured contracts, not undocumented prose blobs.
6. Deterministic software handles deterministic problems.
7. Human approval is required in MK1 v1.
8. Approved evidence is immutable.
9. MongoDB is the system of record; Redis is transport/coordination only.
10. External publication uncertainty is reconciled, never blindly retried.
11. Tenant isolation exists in the domain from day one even if the first deployment boots a single tenant.
12. Platform integrations are capability-driven; manual export is always a valid fallback.
13. Performance is a learning signal, never permission to violate novelty, brand or safety.
14. No important architectural node remains open before a dependent build slice starts.

## V1 outcome

MK1 v1 must support:

- multiple Profiles;
- lightweight Profile onboarding plus inference from examples;
- configurable Batches;
- Editorial Memory and novelty/cooldown enforcement;
- Planner + Research + Writer + Editor + Visual cell;
- single image, carousel, and infographic VisualSpecs;
- deterministic composition plus optional generated visual components;
- deterministic, semantic and visual QA;
- explicit human review and immutable approval;
- durable assets and ZIP/manual export;
- Redis-backed render/publish/analytics job transport;
- automatic LinkedIn publishing where authorized;
- manual publish package for unsupported channels;
- basic metric snapshots and performance summaries.

Motion/video, autonomous approval, broad automatic multi-platform publishing, and advanced optimization remain later-generation slices unless explicitly promoted.

## Read next

- Product thesis: `brainstorming/PRODUCT_THESIS.md`
- MK0 reconciliation: `brainstorming/MK0_TO_MK1_RECONCILIATION.md`
- Product design: `design/PRODUCT.md`
- Architecture: `arch/SYSTEM_ARCHITECTURE.md`
- Design graph: `plan/DESIGN_GRAPH.md`
