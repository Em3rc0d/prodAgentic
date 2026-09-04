# prodAgentic MK1 — Work Execution Directive

Status: **ACTIVE**  
Authority: `main` MK1 Design Freeze + Build Entry Receipt  
Execution phrase: **TAKE THE HUMMER**

This document is the operational handoff for Work. It does not replace the frozen MK1 design; it tells Work how to consume that design and implement it without inventing architecture in code.

---

# 1. Mission

Implement prodAgentic MK1 from the accepted Design Freeze by certified vertical slices, preserving MK0 safety and historical evidence while transferring authority incrementally into the MK1 domain.

The execution law is:

```text
READ
→ VERIFY CURRENT STATE
→ REVIEW SLICE RISKS
→ DEFINE/VERIFY CONTRACTS
→ IMPLEMENT ONE VERTICAL SLICE
→ TEST
→ CERTIFY
→ DOCUMENT
→ REVIEW
→ MERGE
→ NEXT SLICE
```

Do **not** perform a big-bang rewrite.

Do **not** treat the current `backend/` and `frontend/` directory layout as the target architecture merely because it exists.

Do **not** reinterpret MK0 historical outputs as if they already satisfied MK1 typed contracts.

---

# 2. Canonical repository state

Before any implementation, verify all of the following on `main`:

- `mk1/STATUS.md` says `DESIGN FREEZE ACCEPTED` and `TAKE THE HUMMER`;
- `mk1/plan/BUILD_ENTRY_RECEIPT.md` says `PASSED — TAKE THE HUMMER`;
- critical Design Graph nodes are `70 CLOSED / 0 OPEN / 0 REVISIT`;
- MK0 historical freeze is `mk0/freeze-20260831` at `aa64a49ebf96cfbcd5ef9be015796219ac6a1848`;
- canonical MK1 design merge is `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`;
- build-entry merge is present on `main`.

If these receipts are not present, do not begin implementation.

---

# 3. Mandatory reading order before code

Work must read these files from `main` before changing runtime code.

## 3.1 Generation and authority

1. `README.md`
2. `mk1/README.md`
3. `mk1/STATUS.md`
4. `mk1/plan/BUILD_ENTRY_RECEIPT.md`
5. `mk1/plan/BUILD_ENTRY_CRITERIA.md`
6. `mk1/plan/DESIGN_GRAPH.md`

Purpose: understand what MK1 is, what is frozen, what may still be researched, and what `TAKE THE HUMMER` authorizes.

## 3.2 Delivery method

7. `mk1/plan/DELIVERY_PLAN.md`
8. `mk1/plan/VERTICAL_SLICES.md`
9. `mk1/plan/RISK_REGISTER.md`
10. `mk1/build/IMPLEMENTATION_GUIDE.md`
11. `mk1/build/MIGRATION_FROM_MK0.md`
12. `mk1/build/CODE_RULES.md`

Purpose: understand slice order, migration law, code boundaries, feature flags and required evidence.

## 3.3 Product and UX

13. `mk1/design/PRODUCT.md`
14. `mk1/design/INFORMATION_ARCHITECTURE.md`
15. `mk1/design/USER_JOURNEYS.md`
16. `mk1/design/PROFILE_SETUP.md`
17. `mk1/design/CREATE_FLOW.md`
18. `mk1/design/REVIEW.md`
19. `mk1/design/CALENDAR_ANALYTICS.md`
20. `mk1/design/DESIGN.md`

Purpose: prevent backend schemas from leaking into the product experience and preserve the low-friction UX contract.

## 3.4 Domain and architecture

21. `mk1/arch/SYSTEM_ARCHITECTURE.md`
22. `mk1/arch/DOMAIN_MODEL.md`
23. `mk1/arch/STATE_MACHINES.md`
24. `mk1/arch/INVARIANTS.md`
25. `mk1/arch/CONTRACTS.md`
26. `mk1/arch/EDITORIAL_ENGINE.md`
27. `mk1/arch/AGENT_ARCHITECTURE.md`
28. `mk1/arch/VISUAL_SYSTEM.md`
29. `mk1/arch/GOVERNANCE_QA.md`
30. `mk1/arch/INVALIDATION_RULES.md`
31. `mk1/arch/DATA_ARCHITECTURE.md`
32. `mk1/arch/EXECUTION_ARCHITECTURE.md`
33. `mk1/arch/PUBLISHING.md`
34. `mk1/arch/ANALYTICS_LEARNING.md`
35. `mk1/arch/SECURITY_OBSERVABILITY.md`
36. every accepted ADR under `mk1/arch/adr/`

Purpose: understand aggregate ownership, authority boundaries, contracts and non-negotiable invariants before implementation.

## 3.5 Testing and certification

37. `mk1/test/TEST_STRATEGY.md`
38. `mk1/test/GOLDEN_DATASETS.md`
39. `mk1/test/ACCEPTANCE_SCENARIOS.md`
40. `mk1/test/CERTIFICATION.md`

Purpose: know how each slice is proven, not merely implemented.

## 3.6 Evidence/research lanes

41. `mk1/mining-site/README.md`
42. `mk1/mining-site/SOURCE_MAP.md`
43. `mk1/mining-site/EVIDENCE_LEDGER.md`
44. `mk1/mining-site/FINDINGS.md`
45. `mk1/quarries/README.md`
46. `mk1/quarries/REGISTRY.md`

Purpose: distinguish accepted facts from active investigation. A quarry is not authority until promoted through the design/ADR process.

---

# 4. Preflight before S0

Before writing MK1 code, Work must inspect the current MK0 implementation areas affected by S0 and record an implementation map.

At minimum inspect:

```text
backend/models/
backend/db/
backend/core/auth.py
backend/core/context.py
backend/core/container.py
backend/routes/
frontend/app/
frontend/lib/api.ts
frontend/lib/auth.ts
.github/workflows/ci.yml
```

Do not change code during the first inspection pass.

Create the first implementation record:

```text
mk1/build/slices/S0/BUILD_RECORD.md
```

The record must contain:

```text
slice ID
objective
accepted design/ADR dependencies
current MK0 code touched
new modules introduced
migration behavior
feature flags
API/domain contracts
observability
failure paths
rollback strategy
tests required
certification evidence
known limitations
```

Review `mk1/plan/RISK_REGISTER.md` before the slice starts and explicitly note which risks S0 touches.

---

# 5. Branch and PR discipline

One principal branch/PR per vertical slice unless a slice is deliberately split into independently certifiable sub-slices.

Recommended naming:

```text
mk1/s0-foundation-bootstrap-tenant
mk1/s1-profile-v2
mk1/s2-batch-memory-novelty
mk1/s3-structured-agent-cell
mk1/s4-visualspec
mk1/s5-renderer-assetstore
mk1/s6-qa-recovery
mk1/s7-review-approval-v2
mk1/s8-manual-export
mk1/s9-redis-outbox
mk1/s10-calendar-linkedin
mk1/s11-analytics-snapshots
mk1/s12-performance-learning
```

A slice PR must not be merged merely because code compiles.

Every PR must include or link:

- build record;
- tests executed;
- certification record;
- migration evidence when applicable;
- screenshots/snapshots for user-facing changes;
- known limitations;
- rollback path;
- doc/ADR update if an accepted contract changed.

Do not mix unrelated cleanup into functional slice PRs.

---

# 6. Execution sequence

## S0 — Foundation + Bootstrap Tenant

Goal: establish the MK1 authority foundation while leaving MK0 runtime behavior intact.

Implement:

- `TenantContext` resolved server-side;
- deterministic/bootstrap tenant for the current single-admin installation;
- tenant-scoped repository ports for new MK1 entities;
- cross-tenant negative test fixture;
- MK1 module boundaries incrementally, not by mechanical full-repo move;
- MK1 feature-flag registry;
- application-shell/design-token foundation needed by later MK1 screens;
- migration script/verification for bootstrap tenant mapping.

Required proof:

- every new MK1 business document has `tenant_id`;
- new repository access requires tenant scope;
- client cannot choose arbitrary tenant authority;
- migration is idempotent;
- MK0 behavior remains green;
- cross-tenant reads/writes fail in tests.

Do not implement Profile V2 inside S0 beyond interfaces/scaffolding needed by S1.

## S1 — Profile V2

Implement the Profile/ProfileVersion split and low-friction setup flow.

Flow:

```text
Profile Setup UI
→ application service
→ Profile + immutable ProfileVersion
→ Mongo
→ frozen version read by downstream execution
```

Implement:

- reusable Profile identity;
- immutable version snapshots;
- explicit MK0 ContentProfile bridge/migration;
- inference proposal boundary with deterministic fixtures or mocked model;
- example ingestion/reference mechanism consistent with the UX design;
- no OAuth or platform secrets in Profile/ProfileVersion;
- Profile updates create new versions rather than rewriting historical snapshots.

Certify quick setup, inference proposal, version immutability and historical isolation.

## S2 — Batch + Editorial Memory + Novelty

This is the first major new editorial-intelligence slice.

Implement:

```text
Generate next batch
→ BatchPlanner
→ Editorial Memory
→ candidate pool
→ NoveltyEngine
→ diversity selection
→ ContentItems
```

Requirements:

- candidate pool larger than requested output;
- recent approved/scheduled/published concepts included in memory;
- current batch candidates compared with each other;
- novelty remains multi-layered and explainable;
- hard/strong cooldown policy represented explicitly;
- insufficient novelty may return fewer items rather than inventing/repeating content;
- no performance optimization overrides novelty or safety;
- Content Seller, Logan and Tech golden planning fixtures pass.

Do not call the production agent cell until plans are accepted by the planning contract.

## S3 — Structured Four-Agent Text Cell

Implement typed production:

```text
ContentPlan
→ ResearchPack
→ ContentSpec
→ EditorialReview
→ ContentRevision
```

Requirements:

- registered/versioned Pydantic contracts;
- matching controlled TypeScript/OpenAPI types where applicable;
- Planner remains separate from the four-agent production cell;
- Writer cannot publish claims not supported by ResearchPack;
- Editor cannot introduce unsupported claims;
- malformed structured output uses bounded repair/retry;
- domain failures replan/reject rather than blindly retry;
- GenerationRun lineage persists attempts/provider/model/cost/latency/digests;
- process restart can reopen lineage;
- regeneration creates new run/revision provenance rather than overwriting history.

## S4 — VisualSpec V1

Implement the visual intermediate representation before renderer complexity.

Flow:

```text
accepted ContentSpec
→ VisualAgent
→ VisualSpecV1
```

Support V1 formats:

- single image;
- carousel;
- infographic.

Requirements:

- VisualSpec references critical editorial text rather than asking an image model to invent it;
- DesignProfile mapping is deterministic enough for snapshot tests;
- schema validation for page count/canvas/layout/blocks/assets;
- no GIF/short-video expansion in this slice.

## S5 — Renderer + AssetStore

Implement:

```text
VisualSpec
→ RendererPort
→ ChromiumRenderer adapter
→ AssetStore
→ persisted bytes + SHA-256
→ Review preview
```

Requirements:

- exact dimensions and page counts;
- deterministic critical copy composition;
- configured durable asset root;
- restart durability;
- asset hash test vectors;
- high-quality golden renders for Content Seller, Logan and Tech;
- review preview works desktop/mobile;
- renderer failure is observable and recoverable without corrupting text authority.

## S6 — QA + Automatic Recovery

Implement layered QA:

```text
deterministic checks
+ semantic checks
+ visual checks
→ QAReport
→ bounded recovery
→ REVIEWABLE or escalation
```

Requirements:

- clipping/overflow fixture auto-recovers or exhausts a bounded budget;
- claim mismatch blocks review/approval;
- visual failure may preserve valid copy;
- recovery produces new evidence/revision where required;
- Batch may be partially ready and UI reflects it honestly;
- user should not be burdened with recoverable internal failures.

## S7 — Review + ApprovalBundleV2

Implement the governed review boundary.

Flow:

```text
Review
→ edit
→ dependency invalidation
→ required QA
→ explicit Approve
→ immutable ApprovalBundleV2
```

Requirements:

- edits create ContentRevision rather than mutate historical generation output;
- dependency invalidation follows the frozen DAG;
- stale/concurrent approval is blocked;
- approval binds exact text, VisualSpec/asset evidence and hashes;
- approved bytes are immutable authority;
- progressive disclosure UI: simple actions by default, evidence/agent detail under advanced views;
- publishing must never read mutable drafts instead of Approval.

## S8 — Manual Export Package

Implement ManualExport as a real first-class fallback, not an error state.

Flow:

```text
Approval
→ export representation
→ manifest + caption + approved assets + hashes
→ ZIP/package
```

Requirements:

- package derives only from exact Approval;
- hashes verify;
- no secrets included;
- unsupported/unconnected channels can still complete the user's publishing job manually;
- ZIP remains a projection/export, never source of truth.

## S9 — Redis Streams + Mongo Outbox

Introduce durable asynchronous transport without making Redis authoritative.

Flow:

```text
Mongo business intent
→ transactional/consistent outbox record
→ dispatcher
→ Redis Stream
→ consumer group worker
→ domain atomic claim
→ work
→ ACK
```

Implement:

- Redis Streams;
- consumer groups;
- Mongo outbox;
- idempotency operation keys;
- pending-entry recovery;
- bounded retries by failure class;
- DLQ/terminal transport evidence;
- queue lag/job age/retry/DLQ metrics.

Certify:

- Redis loss after outbox does not lose domain work;
- duplicate XADD/delivery is safe;
- worker restart/pending recovery works;
- DLQ does not mark business success.

## S10 — Calendar + LinkedIn Publication

Transfer scheduling/publication authority into MK1.

Flow:

```text
Approval
→ Schedule
→ Mongo outbox
→ Redis
→ publish worker
→ PlatformAdapter/LinkedIn
→ Publication receipt
→ Calendar
```

Requirements:

- Schedule/Publication are destination-specific entities;
- one Approval may target multiple destinations without contaminating ContentItem state;
- exact approved asset bytes are rehashed before upload;
- publication consumes Approval, never mutable revision fields;
- duplicate delivery cannot duplicate a post at the product boundary;
- known provider failure and uncertain outcome are different states;
- after uncertain external success + local crash, enter reconciliation; never blind-retry `PUBLISHING`;
- PlatformCapability drives supported UX;
- MK0 LinkedIn behavior is preserved or superseded with equal/better evidence;
- disable competing MK0 write authority before enabling MK1 write authority for the same content.

External/live publication smoke is allowed only when credentials/environment are legitimately available and the user has authorized the live action. Otherwise certify provider contracts/mocks and record the remaining external gate honestly.

## S11 — Analytics Snapshots

Implement append-only normalized measurement.

Flow:

```text
Publication
→ analytics job
→ provider adapter
→ MetricSnapshot
→ Analytics UI
```

Requirements:

- unsupported/missing metric = unavailable, not zero;
- snapshot freshness visible;
- snapshots append rather than silently overwrite history;
- provider failure degrades safely;
- analytics follows tenant scope and publication identity.

## S12 — PerformanceSummary + Planner Learning

Implement bounded learning, behind a feature flag.

Flow:

```text
MetricSnapshots
→ normalized PerformanceSummary
→ confidence-aware signals
→ Planner tie-breaker
```

Requirements:

- low sample size/confidence prevents strong recommendations;
- Brand/Safety/Novelty/Diversity/Quality outrank Performance;
- performance can never bypass hard novelty or claim safety;
- feature flag disables learning without breaking planning;
- no causal claim from observational metrics unless evidence supports causality.

---

# 7. Phase grouping

For project tracking, map slices to phases:

```text
Phase A — Foundation migration       S0–S1
Phase B — Planning intelligence      S2
Phase C — Structured production      S3
Phase D — Visual production          S4–S5
Phase E — Governance + review        S6–S7
Phase F — Execution/distribution     S8–S10
Phase G — Analytics/learning         S11–S12
Phase H — Production cutover         separate certified cutover
```

S0–S10 produce the minimum governed MK1 content-to-publication path. S11–S12 complete the V1 learning loop.

Do not remove MK0 compatibility code simply because S10 works. Cleanup occurs only after certified cutover and rollback-window completion.

---

# 8. Test obligations per slice

Use `mk1/test/TEST_STRATEGY.md` as authority.

At minimum every slice requires:

- compile/type/lint;
- relevant unit tests;
- contract tests;
- invariant tests;
- regression coverage for touched MK0 behavior;
- documentation/build record.

When applicable add:

### User-facing slice

- happy/error E2E;
- accessibility;
- desktop/mobile snapshots.

### State/storage slice

- migration idempotency;
- restart/persistence;
- optimistic concurrency.

### Queue/worker slice

- duplicate delivery;
- pending recovery;
- restart;
- DLQ/lag observability.

### Publishing slice

- Approval byte verification;
- idempotency/duplicate delivery;
- uncertain crash/reconciliation;
- provider contract mock;
- live smoke only when explicitly authorized.

### Security

- tenant isolation;
- auth/CSRF regression;
- secret redaction;
- prompt-injection fixtures for external research;
- SSRF/path traversal/malformed asset fixtures where relevant.

---

# 9. Certification obligations

For each slice create:

```text
mk1/test/evidence/<slice-id>/CERTIFICATION.md
```

or an equivalent manifest linking CI artifacts.

Required fields:

```text
slice_id
commit_sha
contract/ADR versions
migration version
unit result
contract result
integration result
E2E result when applicable
visual snapshots when applicable
security/tenant result
chaos/recovery result when applicable
observability evidence
known limitations
rollback procedure
review/acceptance state
```

A green generic CI run is necessary but not sufficient.

If certification finds an invariant violation, the slice fails. Do not label it “mostly complete”.

---

# 10. Absolute implementation laws

The following are non-negotiable:

1. No new MK1 business document without `tenant_id`.
2. No route handler publishes directly to an external platform.
3. No agent directly writes authoritative domain state.
4. No publisher reads mutable draft/revision fields instead of Approval.
5. No Redis-only durable business state.
6. No blind retry from uncertain `PUBLISHING` state.
7. No raw remote asset URL becomes approval authority.
8. No registered agent boundary returns an unversioned opaque blob.
9. No critical visual copy is authored only inside an image-generation model.
10. No Profile snapshot contains OAuth tokens/secrets.
11. No new required Profile form field without UX/design justification.
12. No regeneration overwrites historical run/revision provenance.
13. No unsupported metric is silently represented as zero.
14. No feature is done without error path, observability/audit and tests.
15. No architecture-changing implementation merges without corresponding MK1 doc/ADR/design-graph update.

---

# 11. When Work must stop implementation and reopen design

Do not improvise around a material contradiction.

If implementation reveals that an accepted contract is impossible, unsafe or materially wrong:

1. stop relying on the disputed assumption;
2. record concrete evidence under `mk1/mining-site/`;
3. open/update a bounded quarry if investigation is required;
4. set the affected Design Graph node to `REVISIT`;
5. update the relevant design/architecture document;
6. create/amend an ADR;
7. identify downstream contracts affected;
8. re-certify those contracts;
9. only then resume implementation.

Minor implementation choices that do not alter accepted semantics do not require reopening the graph.

---

# 12. When Work may continue autonomously

If a slice satisfies its contracts and certification is green, Work should proceed to the next dependency-ready slice without asking for architectural confirmation again.

Work should ask/escalate only when required by one of these categories:

- a genuine accepted-design contradiction;
- destructive production migration/cutover;
- live external publication or credential-sensitive action requiring explicit authorization;
- unavailable external capability that cannot be truthfully mocked/certified;
- a business/product choice not covered by the frozen design.

Do not pause simply because implementation is large.

---

# 13. Production cutover is a separate gate

Completing S0–S12 does not silently authorize production cutover.

Before cutover, perform the frozen release certification:

1. fresh environment deployment;
2. bootstrap tenant/profile;
3. certified Batch generation;
4. review + ApprovalBundleV2;
5. restart durability of approved state/assets;
6. schedule/manual export;
7. automatic LinkedIn smoke if explicitly authorized and credentials exist;
8. publication receipt or documented external gate;
9. analytics snapshot where capability allows;
10. worker restart proving no duplicate/lost authority;
11. security/tenant certification;
12. rollback/cutover evidence.

Only after the cutover receipt exists may legacy write authority be considered retired. Dead MK0 compatibility cleanup is a later, separate change.

---

# 14. First action after reading this directive

Do **not** start with S1, Redis, agents or visual generation.

Begin with:

```text
S0 — Foundation + Bootstrap Tenant
```

Concrete sequence:

```text
1. sync/read current `main`;
2. verify Build Entry receipt;
3. read all mandatory files listed above;
4. inspect current MK0 S0-relevant runtime without editing;
5. review S0 risks from RISK_REGISTER;
6. create `mk1/s0-foundation-bootstrap-tenant` from current `main`;
7. create `mk1/build/slices/S0/BUILD_RECORD.md`;
8. define/test TenantContext + repository contracts first;
9. implement bootstrap tenant migration + tenant-scoped MK1 repository foundation;
10. add feature flags/module boundaries/design-token shell foundation;
11. run unit/contract/integration/security/regression tests;
12. produce S0 certification evidence;
13. update documentation only if implementation changed accepted contracts;
14. open PR with full evidence;
15. merge only when S0 exit criteria are proven;
16. begin S1 from updated `main`.
```

That is the authorized beginning of MK1 implementation.

**TAKE THE HUMMER.**
