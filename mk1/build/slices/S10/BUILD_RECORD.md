# S10 BUILD RECORD — Calendar + LinkedIn Publication

Status: **FORMALIZED — implementation authorized, certification required before closeout.**

## Authority

Base:

`main@ea6312aff94056788407275d06178e5f579191a8`

S9 is `CERTIFIED/CLOSED` at this authority.

Formalization authority:

- `mk1/build/slices/S10/FORMALIZATION.md`

Frozen dependencies:

- `mk1/plan/VERTICAL_SLICES.md`
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md`
- `mk1/arch/DOMAIN_MODEL.md`
- `mk1/arch/STATE_MACHINES.md`
- `mk1/arch/INVARIANTS.md`
- `mk1/arch/EXECUTION_ARCHITECTURE.md`
- `mk1/arch/PUBLISHING.md`
- `mk1/design/CALENDAR_ANALYTICS.md`
- `mk1/build/MIGRATION_FROM_MK0.md`
- `mk1/test/TEST_STRATEGY.md`
- `mk1/test/ACCEPTANCE_SCENARIOS.md`
- `mk1/plan/RISK_REGISTER.md`

## Objective

Transfer scheduling and LinkedIn publication authority into MK1 without losing S7 Approval immutability, S8 manual fallback, or S9 durable at-least-once transport guarantees.

Canonical flow:

```text
Approval
→ Schedule
→ Mongo outbox
→ Redis pa:publish:v1
→ publish worker
→ Publication atomic claim
→ LinkedIn PlatformAdapter
→ provider receipt / reconciliation
→ Calendar
```

## Current MK0 code touched / superseded by boundary

Inspected legacy surfaces:

- `backend/routes/scheduling.py`
- `backend/routes/publishing.py`
- `backend/core/scheduler.py`
- `backend/core/publication.py`
- `backend/core/linkedin.py`
- `backend/core/linkedin_oauth.py`
- `backend/models/content_run.py`

MK0 currently stores schedule/publication state inside `content_runs`. S10 does not extend this model for MK1. Legacy records remain historical/rollback-compatible.

## New modules planned

Exact filenames may be refined inside the frozen boundaries, but responsibility is fixed:

```text
backend/domain/publishing/
  models.py
  ports.py

backend/application/publishing/
  service.py
  reconciliation.py
  capabilities.py

backend/infrastructure/mongo/
  schedules.py
  publications.py
  connections.py

backend/infrastructure/linkedin/
  adapter.py
  oauth_bridge.py

backend/workers/
  publish_worker.py
  schedule_dispatcher.py

backend/routes/
  calendar.py
  schedules_v2.py
  publications_v2.py
  connections_v2.py

frontend/app/calendar/
frontend/lib/calendar.ts
frontend/lib/publishing.ts
```

No new module may import mutable draft authority as publication input.

## Migration behavior

- introduce tenant-scoped MK1 Connection semantics;
- bootstrap existing global LinkedIn OAuth connection only into the bootstrap tenant through an idempotent migration/bridge;
- encrypted secrets stay infrastructure-only;
- legacy `content_runs` remain readable;
- MK1 schedules/publications are never written inside `content_runs`;
- no cleanup of MK0 compatibility in S10.

## Feature flags

Primary:

- `MK1_PUBLISH_WORKER` — automatic MK1 provider execution; default false.

Prerequisites/fallbacks:

- `MK1_REDIS_TRANSPORT` — required for automatic dispatch/worker execution;
- `MK1_MANUAL_EXPORT` — certified S8 fallback when automatic capability is absent/degraded.

Rollback:

Disabling `MK1_PUBLISH_WORKER` stops new automatic side effects while preserving persisted Schedule/Publication authority and existing receipts.

## API/domain contracts

Authoritative entities:

- `ScheduleV1`;
- `PublicationV1`;
- `PlatformCapabilityV1`;
- `PublicationReceiptV1`;
- tenant-scoped `Connection` boundary.

Planned API surface:

```text
GET    /api/connections/linkedin/status
POST   /api/connections/linkedin/connect
DELETE /api/connections/linkedin
GET    /api/calendar
POST   /api/approvals/{approval_id}/schedules
DELETE /api/schedules/{schedule_id}
GET    /api/schedules/{schedule_id}
GET    /api/publications/{publication_id}
POST   /api/publications/{publication_id}/reconcile
```

Clients never choose arbitrary tenant authority and never submit caption/assets as publication authority.

## Provider surface

S10 automatic LinkedIn V1 certifies:

- text-only member post;
- single-image member post;
- current OAuth write boundary;
- exact Approval/AssetStore SHA verification before upload;
- receipt identity from provider success evidence.

Unsupported formats are capability-gated to Manual Export rather than falsely marked auto-publishable.

Provider API version remains operational configuration and is checked/recorded during certification/release.

## Idempotency

Publication identity is deterministic and versioned from:

```text
operation_version
+ tenant_id
+ approval_id
+ bundle_sha256
+ provider
+ external_identity
+ destination
```

Duplicate transport delivery must produce at most one external publication attempt that crosses the authoritative product claim.

Already `PUBLISHED` identity returns existing receipt with zero external calls.

## Failure paths

- validation/capability/hash failure before external side effect -> safe non-success;
- proven provider rejection without post creation -> `FAILED_SAFE`;
- any outcome where external success cannot be excluded -> `RECONCILIATION_REQUIRED`;
- recovered `PUBLISHING` is never blindly replayed;
- DLQ never means Schedule/Publication success;
- disconnected/expired/unsupported capability is shown honestly in Calendar and may fall back to Manual Export.

## Observability

Required metrics/evidence:

- due schedule age;
- Schedule state counts;
- publication queue lag/job age;
- claim conflicts;
- provider duration/status class;
- asset SHA failures;
- safe failures by class;
- reconciliation count and age;
- publication receipt count;
- provider API version/capability observation;
- connection readiness without secret leakage.

## Risks touched

Primary:

- R10 publication crash duplicates;
- R11 provider API/version drift;
- R13 competing MK0/MK1 source of truth;
- R17 approved asset bytes unavailable/corrupt.

Inherited:

- R09 Redis duplicate/loss semantics;
- R12 tenant isolation.

All mitigations are defined in `FORMALIZATION.md`; no Design Graph REVISIT is required.

## UX

Calendar is the primary distribution surface with:

- Week default;
- Month;
- Queue/List;
- explicit schedule dialog preserving local time + timezone;
- capability-aware automatic/manual actions;
- visible `Needs reconciliation` state with no generic retry;
- labels/icons in addition to color;
- progressive disclosure for provider/evidence detail;
- desktop/mobile/accessibility certification.

## Tests required

See `FORMALIZATION.md` certification matrix. At minimum:

- schema/state/idempotency unit tests;
- real Mongo repository tests;
- real Redis S9 integration/chaos tests;
- tenant negative matrix;
- Approval/asset SHA verification;
- provider contract mocks for text/single-image;
- external-success/local-crash reconciliation fixture;
- duplicate worker concurrency test;
- MK0 regression/supersession evidence;
- Calendar API + browser E2E desktop/mobile/accessibility;
- exact-SHA S10-CERT workflow;
- CI + Docker + S3-S9 regression consensus.

## Certification evidence

Required dedicated workflow:

`.github/workflows/s10-cert.yml`

Evidence bundle must record:

- exact checkout/head SHA;
- provider API version tested;
- domain/repository test output;
- Redis/worker chaos output;
- provider contract output;
- asset/hash verification output;
- migration/secret-boundary evidence;
- Calendar desktop/mobile screenshots or Playwright artifacts;
- source inventory;
- clean checkout proof.

## Live external gate

Live LinkedIn publication is not automatically authorized by S10 work.

Default certification uses provider mocks/contracts. A public smoke requires legitimate credentials plus explicit operator authorization for the exact public action. Without it, the receipt records that live publication was not exercised.

## Known limitations accepted for S10 V1

- automatic LinkedIn V1 is bounded to text-only and single-image posts;
- multi-image/carousel/video/document automation remains capability-gated/manual until separately implemented and certified;
- provider-side automatic reconciliation may be unavailable for member posts under current permissions; indeterminate outcomes remain visibly `RECONCILIATION_REQUIRED`;
- MK0 compatibility remains until production cutover/rollback-window cleanup.

## Implementation sequence

```text
S10.0 Formalization                                  CLOSED
S10.1 Connection boundary + migration               OPEN — NEXT
S10.2 Schedule/Publication domain + repositories    LOCKED behind S10.1 contracts
S10.3 Capability + LinkedIn adapter                 LOCKED
S10.4 S9 dispatcher + publish worker                LOCKED
S10.5 Reconciliation service                        LOCKED
S10.6 Calendar API/read model                       LOCKED
S10.7 Calendar UX                                   LOCKED
S10.8 Chaos/security/browser certification          LOCKED
S10.9 Exact-SHA pre-merge consensus                 LOCKED
S10.10 Merge + post-merge consensus                 LOCKED
```

## Closeout law

Implementation completion does not equal certification.

S10 is `CERTIFIED/CLOSED` only after:

1. all dedicated and regression gates are green on one exact candidate SHA;
2. PR merge is protected with `expected_head_sha`;
3. all applicable workflows are green again on the exact resulting `main` SHA.

Current verdict:

**S10 FORMALIZED: YES**  
**IMPLEMENTATION AUTHORIZED: YES**  
**S10 CERTIFIED/CLOSED: NO**
