# MK1 Design Closure Graph

Status: **CLOSED — SELF-REVIEW PASSED**  
Snapshot date: 2026-09-04

## State vocabulary

- `OPEN` — unresolved and build-blocking when critical.
- `RESEARCHING` — evidence collection underway.
- `PROPOSED` — candidate decision exists, not authoritative.
- `CLOSED` — authoritative contract exists and dependencies are resolved.
- `PARKED` — intentionally deferred, not required by current build slice.
- `REVISIT` — accepted decision reopened by new evidence.

## Critical-node summary

```text
Critical CLOSED: 70
Critical OPEN:    0
Critical REVISIT: 0
Non-blocking PARKED quarry families: 4
```

The graph passed repository consistency self-review. Corrections are recorded in `REVIEW_REPORT.md`.

# G0 — Product

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G0.1 | Product thesis | evidence reconciliation | CLOSED | `brainstorming/PRODUCT_THESIS.md` -> `design/PRODUCT.md` |
| G0.2 | V1 scope/non-goals | G0.1 | CLOSED | `design/PRODUCT.md` |
| G0.3 | Autonomy boundary | G0.1 | CLOSED | `design/PRODUCT.md`, ADR-0008 |
| G0.4 | Product success metrics | G0.1 | CLOSED | `design/PRODUCT.md` |

Unlocks: UX, domain.

# G1 — UX / Product Surface

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G1.1 | Primary navigation | G0 | CLOSED | `design/INFORMATION_ARCHITECTURE.md` |
| G1.2 | Home/Control Center | G1.1 | CLOSED | `design/CONTROL_CENTER.md` |
| G1.3 | Profile Setup | G0, G1.1 | CLOSED | `design/PROFILE_SETUP.md` |
| G1.4 | Create/Batch flow | G0, G1.1 | CLOSED | `design/CREATE_FLOW.md` |
| G1.5 | Review model | G1.1 | CLOSED | `design/REVIEW.md` |
| G1.6 | Calendar/publishing surface | G1.1 | CLOSED | `design/CALENDAR_ANALYTICS.md` |
| G1.7 | Analytics surface | G1.1 | CLOSED | `design/CALENDAR_ANALYTICS.md` |
| G1.8 | Signature design system | G1.1–G1.7 | CLOSED | `design/DESIGN.md` |

Unlocks: frontend slices, Profile/domain semantics, Review/Approval acceptance.

# G2 — Domain

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G2.1 | Tenant root | G0 | CLOSED | `arch/DOMAIN_MODEL.md`, ADR-0003 |
| G2.2 | Profile/ProfileVersion | G1.3, G2.1 | CLOSED | `arch/DOMAIN_MODEL.md` |
| G2.3 | Batch aggregate | G1.4, G2.2 | CLOSED | `arch/DOMAIN_MODEL.md` |
| G2.4 | ContentItem identity | G2.3 | CLOSED | `arch/DOMAIN_MODEL.md`, ADR-0002 |
| G2.5 | GenerationRun | G2.4 | CLOSED | `arch/DOMAIN_MODEL.md` |
| G2.6 | ContentRevision | G2.5, G1.5 | CLOSED | `arch/DOMAIN_MODEL.md` |
| G2.7 | Approval aggregate | G2.6 | CLOSED | `arch/DOMAIN_MODEL.md`, ADR-0008 |
| G2.8 | Schedule/Publication split | G2.7 | CLOSED | `arch/DOMAIN_MODEL.md`, ADR-0009 |
| G2.9 | Asset/QA evidence | G2.6 | CLOSED | `arch/DOMAIN_MODEL.md` |
| G2.10 | State machines | G2.1–G2.9 | CLOSED | `arch/STATE_MACHINES.md` |
| G2.11 | Hard invariants | G2.1–G2.10 | CLOSED | `arch/INVARIANTS.md` |

Unlocks: contracts, persistence, application services.

# G3 — Editorial Intelligence

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G3.1 | Memory eligibility | G2.4, G2.10 | CLOSED | `arch/EDITORIAL_ENGINE.md` |
| G3.2 | Memory dimensions | G3.1 | CLOSED | `arch/EDITORIAL_ENGINE.md` |
| G3.3 | Novelty layers | G3.2 | CLOSED | `arch/EDITORIAL_ENGINE.md`, ADR-0005 |
| G3.4 | Cooldown semantics | G3.3 | CLOSED | `arch/EDITORIAL_ENGINE.md` |
| G3.5 | Candidate pool policy | G3.3 | CLOSED | `arch/EDITORIAL_ENGINE.md` |
| G3.6 | Batch selection order | G3.3–G3.5 | CLOSED | `arch/EDITORIAL_ENGINE.md` |

Calibration thresholds are PARKED, not build-blocking; architecture exposes them as versioned policy.

# G4 — Agent Contracts

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G4.1 | Planner vs four-agent cell | G3 | CLOSED | `arch/AGENT_ARCHITECTURE.md` |
| G4.2 | Research authority/output | G4.1 | CLOSED | `arch/AGENT_ARCHITECTURE.md`, `arch/CONTRACTS.md` |
| G4.3 | Writer authority/output | G4.2 | CLOSED | same |
| G4.4 | Editor authority/output | G4.3 | CLOSED | same |
| G4.5 | Visual authority/output | G4.4 | CLOSED | same |
| G4.6 | Model routing/evidence | G4.1 | CLOSED | `arch/AGENT_ARCHITECTURE.md` |
| G4.7 | Retry taxonomy/budgets | G4.1–G4.6 | CLOSED | `arch/AGENT_ARCHITECTURE.md` |
| G4.8 | Contract registry/versioning | G4.2–G4.5 | CLOSED | `arch/CONTRACTS.md`, ADR-0006 |

# G5 — Visual System

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G5.1 | VisualSpec IR | G4.5 | CLOSED | `arch/VISUAL_SYSTEM.md`, ADR-0007 |
| G5.2 | Critical copy reference rule | G5.1 | CLOSED | `arch/VISUAL_SYSTEM.md` |
| G5.3 | Static V1 strategies | G5.1 | CLOSED | `arch/VISUAL_SYSTEM.md` |
| G5.4 | RendererPort | G5.1 | CLOSED | `arch/VISUAL_SYSTEM.md` |
| G5.5 | Chromium/Playwright adapter | G5.4 | CLOSED | ADR-0012 |
| G5.6 | Asset ownership/digests | G5.4 | CLOSED | `arch/VISUAL_SYSTEM.md`, `arch/DATA_ARCHITECTURE.md` |

Motion/video: PARKED beyond V1.

# G6 — Governance / Approval

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G6.1 | QA pipeline layers | G4, G5 | CLOSED | `arch/GOVERNANCE_QA.md` |
| G6.2 | Severity/block policy | G6.1 | CLOSED | same |
| G6.3 | Automatic recovery | G6.1 | CLOSED | same |
| G6.4 | Dependency invalidation | G2.6, G5, G6.1 | CLOSED | `arch/INVALIDATION_RULES.md` |
| G6.5 | Approval preconditions | G2.7, G6.1 | CLOSED | `arch/GOVERNANCE_QA.md`, ADR-0008 |
| G6.6 | Canonical bundle digest | G6.5 | CLOSED | `arch/CONTRACTS.md` |

# G7 — Data / Execution

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G7.1 | Mongo source of truth | G2 | CLOSED | `arch/DATA_ARCHITECTURE.md`, ADR-0004 |
| G7.2 | Collection/index model | G7.1 | CLOSED | `arch/DATA_ARCHITECTURE.md` |
| G7.3 | AssetStore port/local first | G5.6 | CLOSED | `arch/DATA_ARCHITECTURE.md` |
| G7.4 | Redis Streams transport | G7.1 | CLOSED | `arch/EXECUTION_ARCHITECTURE.md`, ADR-0004 |
| G7.5 | Mongo outbox | G7.4 | CLOSED | same |
| G7.6 | Worker claim/recovery/DLQ | G7.4–G7.5 | CLOSED | `arch/EXECUTION_ARCHITECTURE.md` |

# G8 — Distribution

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G8.1 | Platform capability contract | G2.8 | CLOSED | `arch/PUBLISHING.md`, `arch/CONTRACTS.md` |
| G8.2 | LinkedIn first automatic adapter | G8.1 | CLOSED | `arch/PUBLISHING.md` |
| G8.3 | Manual fallback | G8.1 | CLOSED | ADR-0010 |
| G8.4 | Idempotency identity | G7, G8.1 | CLOSED | `arch/PUBLISHING.md` |
| G8.5 | Reconciliation semantics | G8.4 | CLOSED | ADR-0009 |

Additional automatic platforms: PARKED quarry.

# G9 — Analytics / Learning

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G9.1 | Metric snapshots | G2.8 | CLOSED | `arch/ANALYTICS_LEARNING.md` |
| G9.2 | Normalization boundary | G9.1 | CLOSED | same |
| G9.3 | PerformanceSummary | G9.1–G9.2 | CLOSED | `arch/CONTRACTS.md` |
| G9.4 | Learning priority/guardrails | G3, G9.3 | CLOSED | ADR-0011 |

# G10 — Security / Operations

| Node | Decision | Depends | Status | Authority |
|---|---|---|---|---|
| G10.1 | Tenant-scoped repositories | G2.1 | CLOSED | `arch/SECURITY_OBSERVABILITY.md` |
| G10.2 | Secrets/connection isolation | G2.2, G8 | CLOSED | same |
| G10.3 | Untrusted research boundary | G4.2 | CLOSED | same |
| G10.4 | Asset ingestion safety | G5.6 | CLOSED | same |
| G10.5 | Correlation/log/metrics model | all | CLOSED | same |
| G10.6 | Feature flags/cost budgets | G4, G7 | CLOSED | `arch/EXECUTION_ARCHITECTURE.md`, `arch/SECURITY_OBSERVABILITY.md` |

# Parked quarries

These do **not** block starting MK1 because stable interfaces/policies already exist:

- Q-NOVELTY-01 exact similarity threshold calibration;
- Q-VISUAL-01 advanced visual-pattern benchmark/motion;
- Q-PUBLISH-01 Instagram/TikTok automatic adapter capability research;
- Q-ANALYTICS-01 cross-platform metric normalization depth.

Each quarry can block only the future slice that depends on its promoted result.
