# S2 Certification — Batch + Editorial Memory + Novelty

Certification state: **CERTIFICATION RECEIPT — MERGE APPROVED ONLY AFTER THIS RECEIPT HEAD PASSES CANONICAL CI**

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

## Exact implementation candidate

```text
3aa962e0d1bd378a3fa0eaa1b252dcd0a69affa2
```

Canonical code-candidate CI evidence:

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

## Hardening findings closed before receipt

### Mongo UTC hydration boundary

The original S2 CI exposed a real adapter bug: Mongo BSON datetimes rehydrated by the default Motor/PyMongo configuration were timezone-naive, while planner `now` values were timezone-aware UTC. Novelty cooldown arithmetic therefore failed with an aware/naive subtraction error on real Mongo memory.

The final candidate restores timezone-aware UTC recursively when Mongo planning documents cross into domain models. Regression coverage verifies both Editorial Memory timestamps and nested Batch `TargetWindow` timestamps after persistence/reload.

### Planning-evidence disclosure certification

The original frontend/browser assertion treated content inside a closed native `<details>` as visible without exercising the disclosure. The product behavior was correct; the certification was not. Jest and Playwright now open `Planning evidence` before asserting its contents. Progressive disclosure remains intact.

## Exit-criterion matrix

| Criterion | Candidate evidence | State |
|---|---|---|
| oversized candidate pool before selection | planner/source tests target `max(8, requested*3)`, cap 24 | PASS |
| committed memory collisions caught | hard/strong cooldown fixtures + real-Mongo MK0 published memory | PASS |
| current-batch collisions caught | same-angle/semantic current-batch fixture | PASS |
| genuinely fresh same-topic treatment is not falsely vetoed | same-topic policy + diversity selection | PASS |
| insufficient novelty returns fewer honestly | PARTIAL Batch test + Create UI copy | PASS |
| exact ProfileVersion is frozen | Batch digest/version + ContentItem/ContentPlan assertions | PASS |
| memory rebuild is idempotent | real-Mongo two-refresh count assertion | PASS |
| Mongo timestamps rehydrate as aware UTC | real-Mongo memory + nested Batch reload assertions | PASS |
| tenant isolation remains structural | tenant-B negative Mongo read + tenant-scoped adapters/indexes | PASS |
| Content Seller golden planning | GD-01 fixture | PASS |
| Logan golden planning | GD-02 fixture | PASS |
| Tech golden planning | GD-03 fixture | PASS |
| Batch commit marker does not expose incomplete plan | real-Mongo precommit failure/compensation | PASS |
| frontend Create is low-friction and honest | Jest + production build | PASS |
| desktop/mobile product frame and S2 browser flow | Playwright UI-01-CERT + artifact `9973926294` | PASS |

## Manual final review

Accepted on implementation candidate `3aa962e0d1bd378a3fa0eaa1b252dcd0a69affa2`:

- `EditorialMemoryEntry` remains a read model, never publication authority.
- `REJECTED` memory is not projected by default.
- `READY_FOR_REVIEW` weight is soft (0.6) and cannot veto like committed publication authority.
- Batch and every selected plan/item reference the exact ProfileVersion used during planning.
- `PerformanceSummary` is absent from S2 runtime strategy; missing evidence is not treated as zero performance.
- no S2 route invokes Research/Writer/Editor/Visual, S3 production, or external publication.
- selected `ContentPlanV1.novelty_result_ref` resolves through the persisted planning trace.
- all new business persistence remains tenant-scoped and S2 indexes begin with `tenant_id`.
- Mongo adapter hydration removes timezone ambiguity before datetime values re-enter planning domain models.
- progressive disclosure is preserved; certification now exercises the actual user interaction.

No unresolved contradiction with the frozen S2 contracts or ADRs was found.

## Receipt-head rule

The implementation candidate above passed unchanged canonical CI and manual review. This file and the matching S2 build record bind that evidence into the repository.

The resulting documentation receipt head is **not merge-approved merely because this text exists**. The exact receipt head must itself pass unchanged canonical CI with:

```text
backend full regression
real Mongo S2 persistence/memory/tenant tests
frontend lint + Jest + production build
UI-01-CERT desktop/mobile + S2 Create journey
production backend image build/smoke
```

If that exact receipt head is fully green, this receipt becomes effective and S2 is **CERTIFIED — MERGE APPROVED** without any further code or documentation mutation. If any gate fails, certification remains blocked and the failure must be fixed on a new candidate.

S3 remains unauthorized until S2 is certified and merged.
