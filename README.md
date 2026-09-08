# prodAgentic

prodAgentic is a governed agentic content-production system. It plans, produces, validates, reviews, stores, schedules, publishes, and learns from content for multiple editorial identities while keeping the operator in control.

## Current product state

The active product generation is **MK1**.

Certified/merged slices:

```text
S0 — Foundation + Bootstrap Tenant       ✅
S1 — Profile V2                         ✅
S2 — Batch + Editorial Memory + Novelty ✅
S3 — Structured Agent Cell              ✅
```

Current work:

```text
S4 — VisualSpec V1                      🔨 BUILD ENTRY
S5 — Renderer + AssetStore              ⛔ NOT STARTED
```

S3 product-code certificate:

```text
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

Final S3 documentation descendant / pre-S4-entry main:

```text
2dd152e671667e1377907c53748aec83aaf4796b
```

`mk1/STATUS.md` is the canonical certification ledger. Product-code certificate boundaries and later documentation descendants are intentionally distinguished.

## Certified MK1 journey today

```text
Bootstrap Tenant
    ↓
Profile V2 quick setup
    ↓
immutable ProfileVersion
    ↓
Create / Batch planning
    ↓
Editorial Memory
    ↓
Novelty + diversity
    ↓
ContentPlanV1
    ↓
ResearchPackV1
    ↓
ContentSpecV1
    ↓
EditorialReviewV1
    ↓
ContentRevisionV1(DRAFT)
    ↓
GenerationRun.VISUAL_PLANNING
```

S4 now adds the typed visual intermediate representation. S4 does **not** own render bytes; Chromium rendering/AssetStore belongs to S5.

## S4 target boundary

```text
accepted ContentSpecV1
  + exact ContentRevisionV1
  + frozen ProfileVersion visual policy
        ↓
VisualAgent / deterministic visual policy
        ↓
VisualSpecV1
```

V1 VisualSpec formats:

```text
single_image
carousel
infographic
```

Critical editorial text must reference the accepted ContentSpec instead of being freely invented inside the VisualAgent.

Build authority:

- [`mk1/build/slices/S4/BUILD_RECORD.md`](mk1/build/slices/S4/BUILD_RECORD.md)
- [`mk1/build/slices/S4/ERROR_LEDGER.md`](mk1/build/slices/S4/ERROR_LEDGER.md)
- [`mk1/arch/VISUAL_SYSTEM.md`](mk1/arch/VISUAL_SYSTEM.md)

## Repository hygiene

Canonical branch/PR policy:

- [`mk1/build/REPOSITORY_HYGIENE.md`](mk1/build/REPOSITORY_HYGIENE.md)

Current integration model:

```text
main                     canonical integration authority
mk1/s4-visualspec-v1     active S4 implementation branch
```

There is currently no `developer`/`develop` branch. Historical uncertified/superseded PRs are archived instead of being merged merely to empty the branch list.

## Run locally with Docker

Default local path:

```bash
git pull
docker compose up --build
```

Then open:

```text
http://localhost:3000
```

Default local login:

```text
username: admin
password: local-docker-password-change-me
```

The checked-in local Compose contract starts MongoDB, FastAPI and Next.js with health-gated startup and persistent named volumes.

For WSL native Docker where Windows `localhost` forwarding is unreliable, use the certified launcher documented in:

- [`docs/WSL_NATIVE_DOCKER.md`](docs/WSL_NATIVE_DOCKER.md)

Other canonical runbooks:

- [`docs/DOCKER_LOCAL.md`](docs/DOCKER_LOCAL.md)
- [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md)
- [`mk1/test/LOCAL_ACCEPTANCE.md`](mk1/test/LOCAL_ACCEPTANCE.md)

## Generations

- **MK0** — historical implementation lineage: FastAPI/Next.js product, ContentRun lifecycle, legacy Content Profiles, approval/publishing/storage/release work. It remains evidence/migration authority only where explicitly retained.
- **MK1** — current reconciled generation built around first-class Profiles, Batches, ContentItems, GenerationRuns, Editorial Memory, Novelty, structured agent contracts, VisualSpec, governed QA, queue-based execution, capability-aware distribution, analytics and progressive-disclosure UX.

## MK1 repository method

```text
brainstorming/  exploration and hypotheses; never authoritative by itself
design/         product, UX and visual design contracts
arch/           domain, application and infrastructure architecture
plan/           dependency graph, delivery order, risks and gates
build/          implementation records, slice ledgers and repository hygiene
test/           test strategy, golden datasets and certification evidence
mining-site/    evidence intake, provenance ledger and repository findings
quarries/       scoped investigations that may promote findings upstream
```

Canonical MK1 index: [`mk1/README.md`](mk1/README.md).

## Documentation authority

When documents conflict inside the active MK:

```text
accepted ADR / invariant
        >
architecture contract
        >
design contract
        >
plan
        >
build note
        >
brainstorming / quarry finding
```

Certification receipts plus `mk1/STATUS.md` determine whether a slice actually crossed its gates.

## Required reading order

1. `mk1/README.md`
2. `mk1/STATUS.md`
3. `mk1/build/REPOSITORY_HYGIENE.md`
4. `mk1/brainstorming/PRODUCT_THESIS.md`
5. `mk1/design/PRODUCT.md`
6. `mk1/arch/SYSTEM_ARCHITECTURE.md`
7. `mk1/arch/DOMAIN_MODEL.md`
8. `mk1/arch/INVARIANTS.md`
9. `mk1/arch/CONTRACTS.md`
10. `mk1/arch/AGENT_ARCHITECTURE.md`
11. `mk1/arch/VISUAL_SYSTEM.md`
12. current slice build record + error ledger.

## Build authorization phrase

MK1 uses **“Take the hummer”** to indicate that the graph is sufficiently closed to begin a build slice. It never bypasses exact-SHA testing, slice-specific certification, receipt-head revalidation, exact-head merge or post-merge evidence.
