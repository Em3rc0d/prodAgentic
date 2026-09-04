# MK1 Vertical Slices

Each slice must include domain, API/application, persistence, UX if user-facing, error path, observability, tests and documentation.

# S0 — MK1 Foundation + Bootstrap Tenant

Deliver:

- `TenantContext`;
- bootstrap tenant migration for existing single-admin installation;
- new module boundaries;
- MK1 feature-flag registry;
- design-token/app-shell foundation.

Exit:

- all new MK1 repository queries require tenant scope;
- cross-tenant negative test fixture exists;
- MK0 behavior remains green.

# S1 — Profile V2

Flow:

```text
Profile Setup UI -> API -> Profile/ProfileVersion -> Mongo -> frozen snapshot read
```

Deliver inference boundary with deterministic fixtures/mocked model.

Exit:

- quick setup works;
- examples can produce an inference proposal;
- accepted profile creates immutable ProfileVersion;
- updating profile does not mutate prior version;
- no OAuth secret lives in profile.

# S2 — Batch + Editorial Memory + Novelty

Flow:

```text
Generate next batch -> BatchPlanner -> Memory -> candidates -> novelty/diversity -> ContentItems
```

Exit:

- candidate pool > requested set;
- recent approved/scheduled/published collisions are caught;
- current-batch collisions are caught;
- insufficient novelty may return fewer items honestly;
- Content Seller/Logan/Tech golden planning fixtures pass.

# S3 — Structured Four-Agent Text Cell

Flow:

```text
ContentPlan -> ResearchPack -> ContentSpec -> EditorialReview -> ContentRevision
```

Exit:

- all outputs schema-valid;
- unsupported claims cannot cross Writer/Editor contract tests;
- retries/repairs bounded and evidenced;
- run lineage reopenable after process restart.

# S4 — VisualSpec

Flow:

```text
accepted ContentSpec -> VisualAgent -> VisualSpecV1
```

Exit:

- single image/carousel/infographic specs validate;
- critical text uses ContentSpec references;
- design-profile mapping deterministic enough for snapshots;
- no rendering required yet.

# S5 — Renderer + AssetStore

Flow:

```text
VisualSpec -> ChromiumRenderer -> AssetStore -> Asset hashes -> Preview
```

Exit:

- exact dimensions/page count;
- restart durability under configured root;
- asset hash test vectors;
- high-quality golden renders for all three Profiles;
- desktop/mobile Review preview can show them.

# S6 — QA + Automatic Recovery

Flow:

```text
Revision -> deterministic + semantic + visual QA -> recover -> REVIEWABLE
```

Exit:

- clipping fixture auto-recovers or escalates after budget;
- claim mismatch blocks;
- visual failure preserves valid copy;
- Batch supports partial ready state in UI.

# S7 — Review + ApprovalBundleV2

Flow:

```text
Review -> edit/invalidate -> QA -> Approve -> immutable Approval
```

Exit:

- concurrent/stale approval blocked;
- approved bytes/digests exact;
- edits create revision rather than mutation;
- approval cannot change after creation;
- Review UX uses progressive disclosure.

# S8 — Export Package

Flow:

```text
Approval -> ManualExport -> manifest/caption/assets
```

Exit:

- ZIP is derived from exact Approval;
- hashes verify;
- no secrets;
- unsupported channels still complete user job.

# S9 — Redis Streams + Outbox

Flow:

```text
Mongo intent -> Outbox -> Redis -> worker -> domain claim -> ACK
```

Exit:

- Redis loss/restart does not lose domain work;
- duplicate XADD/delivery safe;
- pending consumer recovery tested;
- DLQ does not mark business success;
- lag metrics exist.

# S10 — Calendar + LinkedIn Publication

Flow:

```text
Approval -> Schedule -> outbox -> Redis -> publish worker -> LinkedIn -> receipt -> Calendar
```

Exit:

- exact approved asset bytes verified before upload;
- duplicate job does not duplicate post at product boundary;
- uncertain crash yields reconciliation state;
- capability/status UI honest;
- MK0 LinkedIn certified behavior preserved or superseded with equal evidence.

# S11 — Analytics Snapshots

Flow:

```text
Publication -> analytics job -> provider -> MetricSnapshot -> Analytics UI
```

Exit:

- missing metrics unavailable, not zero;
- freshness visible;
- snapshots append rather than overwrite;
- provider failure degrades safely.

# S12 — PerformanceSummary + Planner Learning

Flow:

```text
MetricSnapshots -> PerformanceSummary -> Planner tie-breaker
```

Exit:

- low sample confidence prevents strong recommendations;
- hard novelty/safety tests prove performance cannot override them;
- feature flag can disable learning without breaking planning.

# Cutover criterion

S0–S10 constitute the minimum governed content-to-publication MK1 path. S11–S12 complete V1 learning. Production cutover requires all applicable certification, not merely feature completion.
