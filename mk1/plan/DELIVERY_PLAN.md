# MK1 Delivery Plan

Status: **READY AFTER BUILD-ENTRY REVIEW**

## Method

```text
Evidence
 -> Design Freeze
 -> Contract Freeze
 -> Vertical Slice
 -> Certification
 -> Merge
 -> Next Slice
```

Do not build by horizontal layer (“all backend”, then “all frontend”). Every slice proves a user/domain outcome end-to-end.

# Phase A — Foundation migration

Goal: establish MK1 authority without breaking MK0 runtime.

Deliver:

- bootstrap Tenant mapping;
- new domain modules/repositories;
- ProfileVersion V2 path;
- feature flags;
- migration/read compatibility scaffolding;
- MK1 application shell routes/tokens.

No existing public action is removed yet.

# Phase B — Planning intelligence

Deliver:

- Batch/ContentItem persistence;
- Editorial Memory builder;
- taxonomy/alias interface;
- NoveltyEngine;
- CandidatePlanner + batch selector;
- Create progress surface.

Certify against three golden Profiles before agent pipeline migration.

# Phase C — Structured production

Deliver:

- contract registry/Pydantic models;
- ResearchPack;
- ContentSpec;
- EditorialReview;
- GenerationRun/Revision lineage;
- bounded routing/repair evidence.

# Phase D — Visual production

Deliver:

- VisualSpecV1;
- DesignProfile mapping;
- ChromiumRendererAdapter;
- AssetStore integration;
- single-image/carousel/infographic outputs;
- visual regression fixtures.

# Phase E — Governance + review

Deliver:

- deterministic/semantic/visual QA;
- automatic recovery;
- Review cockpit;
- dependency invalidation;
- ApprovalBundleV2.

At this phase the content-authority portion of MK1 is complete.

# Phase F — Durable execution/distribution

Deliver:

- Mongo outbox;
- Redis Streams transport;
- render/publish/analytics worker harness;
- Schedule migration;
- PlatformCapability;
- LinkedIn adapter migration;
- ManualExport;
- reconciliation UI.

# Phase G — Analytics/learning

Deliver:

- MetricSnapshot;
- analytics worker;
- normalized PerformanceSummary;
- Analytics UI;
- Planner tie-breaker integration behind feature flag.

# Phase H — Cutover

Requirements:

- MK1 golden/E2E/chaos certification green;
- MK0 authoritative write paths either migrated or disabled by flags;
- rollback strategy proven;
- no duplicate authority between legacy `posts` and MK1 entities;
- release runbook updated;
- production smoke evidence captured.

Only after cutover may dead MK0 compatibility code be removed in a separate cleanup slice.
