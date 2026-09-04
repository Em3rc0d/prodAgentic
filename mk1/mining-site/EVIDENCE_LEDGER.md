# MK1 Evidence Ledger

Observation baseline: **2026-09-04**

| ID | Provenance | Evidence | MK1 relevance |
|---|---|---|---|
| E-MK0-001 | OBSERVED | `backend/models/content_run.py` defines lifecycle, stage snapshots, visual, approval, schedule and publication snapshots on `ContentRun`. | Confirms MK0 central aggregate and motivates MK1 split. |
| E-MK0-002 | OBSERVED | `backend/models/content_profile.py` defines reusable versioned Content Profiles and `snapshot()`. | Preserve profile versioning/snapshot invariant. |
| E-MK0-003 | OBSERVED | `backend/agents/orchestrator.py` runs research -> write -> edit -> visual per selected idea and persists stage output strings. | MK1 requires batch planning and structured contracts. |
| E-MK0-004 | OBSERVED | `docs/changes/PR-APPROVAL-01.md` freezes exact approved text/visual choice with digests and optimistic concurrency. | Preserve immutable human authority boundary. |
| E-MK0-005 | OBSERVED | `docs/changes/PR-PUBLISH-01.md` publishes from the approval snapshot and verifies visual bytes immediately before upload. | Preserve approved-byte publication invariant. |
| E-MK0-006 | OBSERVED | `docs/changes/PR-SCHEDULE-01.md` persists schedules in Mongo and forbids automatic replay of uncertain `PUBLISHING`. | Preserve source-of-truth/reconciliation semantics; change transport. |
| E-MK0-007 | OBSERVED | `docs/changes/PR-PROD-02.md` defines `PRODAGENTIC_ASSET_ROOT` as durable product-owned visual storage. | Wrap in AssetStore port rather than discard. |
| E-MK0-008 | OBSERVED | `docs/changes/PR-PROD-01.md` states MK0 is single-admin and not multi-user tenancy/RBAC. | MK1 must add tenant scope without pretending current auth already provides it. |
| E-MK0-009 | OBSERVED | `backend/requirements.txt` contains FastAPI, Mongo clients, Pydantic, Google GenAI and HTTPX; no Redis client is present. | Redis is an MK1 addition, not an existing capability. |
| E-MK0-010 | OBSERVED | `frontend/package.json` uses Next.js 16.3.3, React 19.2.4 and Playwright test tooling. | Keep frontend platform; browser tooling can inform renderer verification. |
| E-MK0-011 | OBSERVED | `frontend/app/` contains create/root, library, profiles, publishing and scheduling surfaces. | MK1 information architecture is a deliberate replacement, not documentation of current UI. |
| E-MK0-012 | OBSERVED | `gptContext.md` describes the original product as a LinkedIn-focused multi-agent content engine. | Shows historical product scope and why MK1 needs a new product contract. |
| E-USER-001 | OFFICIAL | 2026-09-04 accepted direction: signature exterior, Formula-1-like internal control metaphor, low-friction user setup, sensors/fallbacks/pit-team behavior. | Drives product and UX principles. |
| E-USER-002 | OFFICIAL | 2026-09-04 accepted repository lifecycle: `brainstorming`, `design`, `arch`, `plan`, `build`, `test`, `mining-site`, `quarries`; previous work belongs to MK0 and new work to MK1. | Defines documentation topology and generation boundary. |
| E-USER-003 | OFFICIAL | User requires enough design closure to explicitly reach “Take the hummer” before build starts. | Creates build-entry gate. |

## Evidence hygiene

When a fact changes, append a new evidence row rather than rewriting old observation history. Architecture may then use ADR revisit conditions to decide whether the change matters.
