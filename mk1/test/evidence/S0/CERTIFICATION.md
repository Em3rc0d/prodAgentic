# S0 Certification — Foundation + Bootstrap Tenant

Certification state: **CANDIDATE — AWAITING CI/REVIEW**

Slice: `S0`

Branch: `mk1/s0-foundation-bootstrap-tenant`

Code commit: `b50b9ecb72004207bd50d0925b1ad98862e495ce`

## Authority versions

- Design Freeze merge: `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`
- Execution directive base: `f721c1d1925838b691a443af739d80f7faad7c99`
- ADR-0001: accepted 2026-09-04
- ADR-0003: accepted 2026-09-04
- Migration: `mk1_s0_bootstrap_tenant_v1`

## Exit-criterion matrix

| Criterion | Evidence | Candidate result |
|---|---|---|
| new MK1 business documents carry `tenant_id` | `Tenant` schema + scoped insert tests | PASS |
| new repository access requires tenant scope | constructor requires `TenantContext`; query assertions | PASS |
| client cannot choose tenant authority | middleware/header-negative test | PASS |
| migration is idempotent | two-pass unit + real-Mongo CI test | LOCAL PASS / CI PENDING |
| cross-tenant access fails | read/write/update negative matrix + real-Mongo isolation | LOCAL PASS / CI PENDING |
| MK0 remains green | focused auth/index regression + full CI | FOCUSED PASS / FULL CI PENDING |
| app-shell/token foundation exists | Jest IA/token contract + Next build | PASS |

## Local evidence

Environment: Python 3.12 local sandbox for focused tests; Next.js 16.3.3 / Node
runtime supplied by workspace. Canonical CI uses Python 3.11 and Mongo 7.

```text
Python compile: PASS
Full backend regression: 119 passed
Mongo-only integration gates locally: 3 skipped (MONGO_TEST_URI unavailable)
Frontend lint: PASS
Frontend Jest: 8 suites, 26 tests passed
Frontend production build: PASS
git diff --check: PASS
```

The full backend suite passed after removing the workspace-injected network proxy
variables so provider-construction tests matched CI semantics. The sandbox has no
Mongo process; the repository CI job supplies Mongo and the canonical Python
version, so its result remains required before this record becomes `CERTIFIED`.

## Security evidence

- arbitrary `X-Tenant-ID` does not affect resolved context;
- cross-tenant criteria and inserts fail before persistence;
- tenant removal/replacement updates fail;
- explicit existing tenant assignments are not overwritten by migration;
- master feature gate forces child authority paths off;
- no secrets are introduced into Tenant, context, UI tokens or logs.

## Observability evidence

- migration report contains migration ID, tenant ID, per-collection matched,
  modified and missing counts, completion time and verification verdict;
- startup emits a bounded safe summary;
- future MK1 layers receive tenant/actor correlation through `TenantContext`.

## Recovery and rollback

The migration is additive and idempotent. Disable `MK1_ENABLED` and the optional
frontend shell flag for immediate authority rollback. Keep tenant metadata unless
a verified database snapshot restore is explicitly required.

## Known limitations

- no local real-Mongo evidence in this workspace;
- no visible MK1 screen is activated, so visual snapshots are deferred to the
  first slice that activates the shell and routes;
- reviewer acceptance and PR checks remain pending.

## Certification decision

Do not merge or mark S0 certified until:

1. GitHub backend, frontend and browser-required checks complete successfully;
2. the real-Mongo S0 integration test passes in CI;
3. PR review confirms no tenant bypass in the new MK1 repository boundary;
4. this record is updated with immutable commit/check evidence.
