# PHASE H FORMALIZATION — Production Cutover

Status: **FROZEN FOR IMPLEMENTATION**

Base authority:

`main@f71c44eda4cf9769c9eb216469fbcd741e789220`

S0–S12 are `CERTIFIED/CLOSED` at this authority.

## Objective

Cut production authority from MK0 compatibility writes to the certified MK1 path without deleting historical MK0 data or dead-code cleanup in the same change.

Canonical production authority:

```text
ProfileV2
→ BatchPlanner
→ structured production
→ VisualSpec/render
→ QA/recovery
→ Review/ApprovalV2
→ ManualExport OR Schedule/PublicationV1
→ MetricSnapshotV1
→ PerformanceSummaryV1
```

## Frozen cutover laws

1. Production cutover is explicit and reversible. `MK1_PRODUCTION_CUTOVER=true` is the cutover switch.
2. Cutover may activate only when every certified MK1 child authority required for V1 is enabled. Misconfigured partial cutover fails closed at startup.
3. When cutover is active, MK0 historical reads remain available but MK0 mutation/generation/publication routes are rejected.
4. The side-effectful legacy `GET /api/pipeline/stream` is treated as a write and is rejected during cutover.
5. MK0 scheduler execution remains disabled whenever MK1 publication authority is enabled.
6. Legacy `posts`, `content_runs`, and `content_profiles` collections remain historical/readable during the rollback window; Phase H does not delete or rewrite them.
7. New production content authority must not be dual-written into legacy `posts`.
8. Rollback requires no schema reversal: disable `MK1_PRODUCTION_CUTOVER`, disable the MK1 authority flags being rolled back, and restart. Historical MK0 code/data remain intact until a later cleanup slice.
9. Production configuration must retain auth, secure cookies, canonical HTTPS origins, explicit CORS, durable asset root, Mongo, and Redis requirements.
10. Provider/public side effects remain separately authorized. Cutover certification does not imply permission to create a real LinkedIn post.
11. A missing LinkedIn live smoke is an explicit external gate, not fabricated success. Manual export remains a certified distribution path.
12. Cleanup/removal of MK0 compatibility code is forbidden in Phase H.

## MK0 write boundary

During cutover, reject these legacy authorities before route logic executes:

```text
POST   /api/ideas
GET    /api/pipeline/stream
POST   /api/visual-renders
PATCH  /api/content-runs/{...}
POST   /api/content-runs/{...}/approve
POST   /api/content-runs/{...}/publish
POST   /api/content-runs/{...}/schedule
DELETE /api/content-runs/{...}/schedule
POST   /api/content-profiles
PATCH  /api/content-profiles/{...}
POST   /api/content-profiles/{...}/default
DELETE /api/content-profiles/{...}
PATCH  /api/posts/{...}
DELETE /api/posts/{...}
```

GET historical inspection routes remain readable.

The boundary returns `410 Gone` with a stable machine-readable code `MK0_WRITE_AUTHORITY_RETIRED` and identifies the MK1 replacement authority at a category level without leaking data.

## Cutover readiness surface

Add public, non-secret health evidence:

```text
GET /health/cutover
```

It reports only:

- cutover active/inactive;
- safe feature-flag snapshot;
- database readiness;
- MK0 write authority state;
- MK0 scheduler state;
- MK1 publish/analytics worker state;
- overall `READY` / `NOT_READY`.

No token, credential, tenant data, provider post identifier, or user content may appear.

## Production-like release candidate

Phase H certification adds a fresh Docker Compose cutover overlay that starts from empty disposable volumes with:

- `PRODAGENTIC_ENV=production`;
- production auth contract enabled;
- secure cookie / SameSite=None;
- canonical HTTPS frontend/CORS origins;
- durable Mongo + Redis + assets;
- all certified MK1 flags enabled;
- `MK1_PRODUCTION_CUTOVER=true`;
- LinkedIn static fallback disabled;
- no real provider credentials required.

The smoke must prove startup, `/health/live`, `/health/cutover`, auth boundary, legacy write rejection, historical read availability, Mongo/Redis persistence across restart, and rollback behavior in a separate process/configuration test.

## Release certification requirements

The frozen `mk1/test/CERTIFICATION.md` release checklist is satisfied as follows:

1. fresh environment deploy — Phase H disposable production-mode Compose;
2. bootstrap tenant/profile — integrated Phase H backend test on fresh Mongo;
3. generate certified Batch — integrated Phase H backend test through MK1 planning;
4. review/approval — reuse certified S6/S7 plus integrated authority-chain assertions;
5. restart durability of approved assets/state — Phase H restart + S5/S7 persistence regressions;
6. schedule/export — S8/S10 regressions plus Phase H authority assertions;
7. automatic LinkedIn smoke — only if separately authorized credentials/environment exist;
8. publication receipt or documented external gate — explicit `NOT_EXERCISED / OPERATOR_AUTH_REQUIRED` when no live authorization exists;
9. analytics snapshot — S11 contract/runtime regression; live provider read remains capability-dependent;
10. restart workers/no duplicate authority — S9–S11 regressions + cutover restart;
11. security tenant tests — base CI/S0+ and Phase H auth/cutover boundary tests;
12. rollback/cutover evidence — dedicated Phase H tests + runbook.

## Certification matrix

One immutable Phase H candidate must pass **13/13** exact-SHA workflows pre-merge:

```text
CI
Docker Compose Local
S3
S4
S5
S6
S7
S8
S9
S10
S11
S12
PHASE-H Production Cutover Cert
```

After merge, the same 13 workflows must pass again on the exact resulting `main` SHA with zero failures.

## Implementation sequence

```text
H.0  formalization                                CLOSED BY THIS RECORD
H.1  cutover flag + fail-closed configuration     NEXT
H.2  legacy write authority boundary              LOCKED
H.3  cutover health/readiness evidence            LOCKED
H.4  production-mode Compose overlay              LOCKED
H.5  rollback + release runbook                    LOCKED
H.6  integrated fresh-environment tests            LOCKED
H.7  Phase-H exact-SHA workflow                    LOCKED
H.8  exact-SHA pre-merge consensus                 LOCKED
H.9  exact-head merge + exact-main 13/13 recert    LOCKED
H.10 external receipt / closure                    LOCKED
```

## Merge terminology

Canonical wording for Phase H is **“exact-head merge, followed by exact-main 13/13 recertification.”**

An exact-head merge means that the PR head merged into `main` is the exact candidate SHA that passed the pre-merge certification matrix. A compare-and-swap guard such as `expected_head_sha` should be used when the merge interface supports it.

This term does **not** assert that GitHub Branch Protection or repository rulesets are enabled. The post-certification agnostic audit on 2026-09-10 observed neither on `main`; therefore historical shorthand such as “protected merge” must be interpreted only as an exact-head merge guard, not as GitHub protected-branch enforcement.

## Closure law

Phase H is `CERTIFIED/CLOSED` only after:

1. one immutable candidate SHA passes all 13 pre-merge workflows;
2. the head merged into `main` is exactly that certified candidate SHA; use an `expected_head_sha`-style compare-and-swap guard when the merge interface supports it;
3. all 13 workflows pass on the resulting exact `main` SHA;
4. production/provider gates not exercised are named explicitly rather than assumed;
5. the final receipt is externalized in the PR so the certified tree is not mutated.

Only after this receipt may a separate cleanup slice consider removing MK0 compatibility code after the rollback window expires.
