# S2 Certification — Batch + Editorial Memory + Novelty

Certification state: **IMPLEMENTED — AWAITING EXACT-SHA CI**

Slice: `S2`

Branch: `mk1/s2-batch-memory-novelty`

Base: `main@bfa64cb7e03e2344be80a789f0871bbac2bbbcea`

## Authority

- S1 certified merge: `bfa64cb7e03e2344be80a789f0871bbac2bbbcea`
- `mk1/design/CREATE_FLOW.md`
- `mk1/arch/EDITORIAL_ENGINE.md`
- `mk1/arch/DOMAIN_MODEL.md`
- `mk1/arch/INVARIANTS.md`
- `mk1/arch/CONTRACTS.md`
- `mk1/arch/DATA_ARCHITECTURE.md`
- `mk1/plan/VERTICAL_SLICES.md`
- `mk1/test/GOLDEN_DATASETS.md`

## Exit-criterion matrix

| Criterion | Candidate evidence | State |
|---|---|---|
| oversized candidate pool before selection | planner/source tests target `max(8, requested*3)`, cap 24 | AWAITING CI |
| committed memory collisions caught | hard/strong cooldown fixtures + real-Mongo MK0 published memory | AWAITING CI |
| current-batch collisions caught | same-angle/semantic current-batch fixture | AWAITING CI |
| genuinely fresh same-topic treatment is not falsely vetoed | same-topic policy + diversity selection | AWAITING CI |
| insufficient novelty returns fewer honestly | PARTIAL Batch test + Create UI copy | AWAITING CI |
| exact ProfileVersion is frozen | Batch digest/version + ContentItem/ContentPlan assertions | AWAITING CI |
| memory rebuild is idempotent | real-Mongo two-refresh count assertion | AWAITING CI |
| tenant isolation remains structural | tenant-B negative Mongo read | AWAITING CI |
| Content Seller golden planning | GD-01 fixture | AWAITING CI |
| Logan golden planning | GD-02 fixture | AWAITING CI |
| Tech golden planning | GD-03 fixture | AWAITING CI |
| Batch commit marker does not expose incomplete plan | real-Mongo precommit failure/compensation | AWAITING CI |
| frontend Create is low-friction and honest | Jest + production build | AWAITING CI |
| desktop/mobile product frame and S2 browser flow | Playwright UI-01-CERT | AWAITING CI |

## Properties requiring manual final review

- `EditorialMemoryEntry` remains a read model, never publication authority.
- `REJECTED` memory is not projected by default.
- `READY_FOR_REVIEW` weight is soft (0.6) and cannot veto like committed publication authority.
- Batch and every selected plan/item reference the exact ProfileVersion used during planning.
- `PerformanceSummary` is absent from S2 runtime strategy; missing evidence is not treated as zero performance.
- no S2 code invokes Research/Writer/Editor/Visual or external publication.
- selected `ContentPlanV1.novelty_result_ref` resolves through the persisted planning trace.
- all new business persistence remains tenant-scoped.

## Candidate evidence rule

No SHA is certified merely because implementation is complete. A candidate must pass unchanged canonical CI with:

```text
backend full regression
real Mongo S2 persistence/memory/tenant tests
frontend lint + Jest + production build
UI-01-CERT desktop/mobile + S2 Create journey
production backend image build/smoke
```

After a candidate passes and manual review accepts it, this receipt is updated with the exact implementation SHA, CI run/job/artifact evidence and final findings. That receipt commit itself must then pass unchanged exact-head CI before S2 may become **CERTIFIED — MERGE APPROVED**.

S3 remains unauthorized until S2 is certified and merged.
