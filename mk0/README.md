# MK0 — Historical implementation lineage

MK0 is the product generation that exists in the repository before the MK1 reconciliation of 2026-09-04.

It is intentionally preserved rather than rewritten. Its implementation currently lives primarily in the repository-level `backend/`, `frontend/`, `.github/`, and `docs/` directories.

## What MK0 proved

MK0 established several invariants that MK1 deliberately retains:

- a persistent generation record exists before the full pipeline completes;
- reusable Content Profiles are versioned and frozen into generation snapshots;
- an explicit human action is required before content becomes publishable;
- the approval bundle freezes exact text and optional exact visual evidence with SHA-256 digests;
- a publisher reads the approved bundle rather than mutable review fields;
- approved visual bytes are checked before external publication;
- scheduling is a trigger over approval, not a second content authority;
- a `PUBLISHING` crash boundary is not blindly replayed;
- local product-owned visual bytes can be placed under a durable asset root;
- production security and release checks were introduced around the single-admin deployment.

## Known structural limits

MK0 is not the target domain for MK1:

- `ContentRun` carries generation, review, approval, schedule and publication concerns in one aggregate;
- generation is principally a linear per-piece pipeline;
- idea generation is not a first-class governed Batch planning process;
- there is no first-class Editorial Memory / Novelty subsystem;
- visual intent is mostly prompt-oriented rather than represented through a stable visual intermediate representation;
- no Redis transport exists in the current Python dependency set;
- scheduling is application-lifespan polling over Mongo rather than a dedicated transport boundary;
- the product UI exposes implementation-era surfaces (`Library`, `Publishing`, `Scheduling`) rather than a reconciled user journey;
- the release is single-admin and explicitly not multi-tenant/RBAC.

## MK0 source map

Primary evidence is retained in:

```text
backend/models/content_run.py
backend/models/content_profile.py
backend/agents/orchestrator.py
docs/changes/PR-RUN-01.md
docs/changes/PR-RUN-02.md
docs/changes/PR-APPROVAL-01.md
docs/changes/PR-PROFILE-01.md
docs/changes/PR-PUBLISH-01.md
docs/changes/PR-SCHEDULE-01.md
docs/changes/PR-PROD-01.md
docs/changes/PR-PROD-02.md
```

MK1 decisions that reuse MK0 behavior must cite the corresponding evidence in `mk1/mining-site/EVIDENCE_LEDGER.md`.
