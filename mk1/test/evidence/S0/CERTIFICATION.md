# S0 Certification — Foundation + Bootstrap Tenant

Certification state: **CERTIFIED — MERGE APPROVED**

Slice: `S0`

Branch: `mk1/s0-foundation-bootstrap-tenant`

Reviewed code head: `74056ec8930aecd61ad771da94076046dc95a9c8`

Canonical CI: run `33892749948` / CI `#677`

## Authority versions

- Design Freeze merge: `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`
- Build-entry / Work directive baseline: `f721c1d1925838b691a443af739d80f7faad7c99`
- ADR-0001: modular monolith, accepted 2026-09-04
- ADR-0003: tenant scope, accepted 2026-09-04
- Migration: `mk1_s0_bootstrap_tenant_v1`

## Exit-criterion matrix

| Criterion | Evidence | Result |
|---|---|---|
| new MK1 business documents carry `tenant_id` | `Tenant` schema + scoped insert tests | PASS |
| new MK1 repository access requires tenant scope | repository constructor requires immutable `TenantContext`; query assertions | PASS |
| client cannot choose tenant authority | auth middleware derives context from trusted actor; hostile tenant header ignored | PASS |
| migration is additive/idempotent | two-pass unit fixture + real-Mongo CI integration test | PASS |
| invalid legacy scope fails closed | null/empty-scope unit regression + real-Mongo null-scope regression | PASS |
| cross-tenant reads/writes/updates fail | negative matrix + real-Mongo isolation fixture | PASS |
| tenant authority cannot be renamed/mutated | `$unset`, replacement, cross-tenant and `$rename -> tenant_id.*` tests | PASS |
| MK0 runtime remains green | complete backend/frontend/browser CI on reviewed head | PASS |
| app-shell/token foundation exists without authority transfer | Jest/token contract + production build; shell flag off by default | PASS |

## Canonical CI evidence

CI run `33892749948` executed against exact head:

```text
74056ec8930aecd61ad771da94076046dc95a9c8
```

Results:

```text
backend-test             PASS
  dependency audit       PASS
  smoke import           PASS
  compile                PASS
  full backend tests     PASS
  real Mongo S0 gates    PASS (part of backend test suite)
  production image build PASS
  production image smoke PASS

frontend-test            PASS
  dependency audit       PASS
  lint                   PASS
  Jest                   PASS
  API-origin gate        PASS
  production build       PASS

UI-01-CERT browser       PASS
  production backend     PASS
  production frontend    PASS
  desktop/mobile browser PASS
  evidence upload        PASS
```

The browser job completed successfully at `2026-09-04T16:05:52Z`.

## Manual tenant-boundary review

A dedicated multitenant review was performed after the first green candidate rather than treating CI as sufficient.

Two edge cases were discovered and resolved before certification:

1. **Invalid existing tenant scope could pass migration verification.** The original migration only counted missing `tenant_id`; documents with `tenant_id: null` or `tenant_id: ""` could survive while the report said verified. The report now carries `invalid_after_migration`, and verification requires both missing and invalid counts to be zero. Existing malformed explicit assignments are preserved for operator review rather than silently reassigned.
2. **Mongo `$rename` destination subpaths could target tenant authority.** The scoped repository blocked `tenant_id` mutation and exact rename-to-`tenant_id`, but did not explicitly reject a destination such as `tenant_id.shadow`. It now rejects rename destinations equal to `tenant_id` or under `tenant_id.*`.

Regression coverage was added for both findings. See `TENANT_BOUNDARY_REVIEW.md`.

## Security evidence

- `TenantContext` is server-derived from verified session identity or trusted auth-disabled development identity;
- headers/query/body do not provide tenant authority;
- repository queries are structurally AND-scoped to the context tenant;
- cross-tenant criteria/documents fail before Mongo writes;
- tenant removal, replacement and rename mutation fail;
- malformed legacy scope causes migration verification failure;
- existing non-empty tenant assignments are not overwritten;
- master MK1 feature gate forces child authority paths off when disabled;
- no connection secrets/tokens are introduced into tenant/domain snapshots or logs.

## Persistence / migration evidence

The migration:

1. resolves one stable server-side bootstrap tenant;
2. upserts the Tenant with `$setOnInsert`;
3. adds `tenant_id` only where the field is absent on mapped MK0 collections;
4. preserves existing assignments;
5. verifies missing and invalid scope counts;
6. is safe to re-run and produces zero modifications on an already-mapped valid dataset.

Mongo CI proves the forward migration and tenant-isolation behavior against a real Mongo service.

## Observability evidence

The migration report exposes:

- migration ID;
- tenant ID;
- per-collection matched counts;
- modified counts;
- missing counts;
- invalid counts;
- verification verdict;
- completion time.

Startup emits a bounded non-secret summary, and `TenantContext` carries tenant/actor correlation for subsequent MK1 application layers.

## Recovery / rollback

Immediate authority rollback:

```text
MK1_ENABLED=false
NEXT_PUBLIC_MK1_SHELL unset/false
```

The migration is additive. Added valid tenant metadata and indexes should normally remain because removing isolation metadata increases risk and does not improve MK0 compatibility. Exact physical rollback requires an independently justified database snapshot restore.

## Known limitations

- S0 establishes one bootstrap Tenant; team membership/RBAC is not S0 scope.
- MK0 routes remain legacy authority until their owning MK1 slices transfer them.
- the MK1 shell remains inactive by default; later user-facing slices must certify their visible routes/states.
- production backup/restore and production cutover are separate release gates.

These limitations do not violate S0 exit criteria.

## Certification decision

S0 satisfies its frozen exit criteria, the reviewed tenant boundary has no known blocking bypass, and CI #677 is green on the reviewed code head.

**Verdict: CERTIFIED — MERGE APPROVED.**
