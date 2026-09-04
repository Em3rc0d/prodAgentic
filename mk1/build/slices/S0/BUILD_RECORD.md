# S0 Build Record — Foundation + Bootstrap Tenant

Status: **IMPLEMENTED — CERTIFICATION IN PROGRESS**

Branch: `mk1/s0-foundation-bootstrap-tenant`

Started from: `main@f721c1d1925838b691a443af739d80f7faad7c99`

Implementation commit: `69204e331816a6cdf6868946a6ced645b7098095`

## Objective

Install the first MK1 authority boundary without changing MK0 content-generation,
approval, scheduling or publication semantics:

```text
authenticated server identity
  -> TenantContext
  -> tenant-scoped MK1 repository adapter
  -> Mongo query/write with mandatory tenant predicate
```

The current single-admin deployment maps to one deterministic bootstrap Tenant.

## Accepted authority

- `mk1/arch/adr/ADR-0001-MODULAR-MONOLITH.md`
- `mk1/arch/adr/ADR-0003-TENANT-SCOPE.md`
- `mk1/arch/INVARIANTS.md` rules 1–4
- `mk1/arch/DATA_ARCHITECTURE.md`
- `mk1/arch/SECURITY_OBSERVABILITY.md`
- `mk1/build/MIGRATION_FROM_MK0.md` Stage 1
- `mk1/plan/VERTICAL_SLICES.md` S0
- `mk1/test/TEST_STRATEGY.md`

No accepted contract or ADR was changed by this slice.

## MK0 implementation map inspected

| Area | Observed MK0 behavior | S0 treatment |
|---|---|---|
| `backend/core/auth.py` | signed single-admin session + CSRF boundary | preserve; attach server-derived `TenantContext` after authentication |
| `backend/core/context.py` | generation context has no tenant authority | preserve; MK1 tenant context is a separate domain type |
| `backend/core/container.py` | provider/pipeline composition root | preserve |
| `backend/db/mongo.py` | Mongo connection + legacy publication index | add separate S0 indexes and bootstrap migration after legacy index setup |
| `backend/db/content_runs.py` | direct MK0 `content_runs` persistence | preserve untouched; do not pretend it is an MK1 repository |
| `backend/models/` | MK0 ContentProfile/ContentRun/Post models | preserve historical semantics |
| `backend/routes/` | MK0 routes directly query Mongo | preserve until their authority moves in later slices |
| `frontend/app/` | MK0 Create/Library/Profile/Publish/Schedule IA | preserve as default UI |
| `frontend/lib/api.ts`, `auth.ts` | MK0 API/session clients | preserve untouched |
| `.github/workflows/ci.yml` | Python 3.11 + Mongo service + frontend gates | reuse; real Mongo S0 gate added to existing integration suite |

## New modules

```text
backend/domain/tenants/
  models.py                  Tenant, TenantStatus, TenantContext
  ports.py                   TenantRepositoryPort

backend/application/tenancy/
  context.py                 server-side bootstrap resolution/dependency
  bootstrap.py               idempotent migration + verification report

backend/infrastructure/mongo/
  tenants.py                 MongoTenantRepository
  scoped_repository.py       mandatory-scope base adapter for new MK1 repos

backend/core/feature_flags.py
backend/scripts/migrate_mk1_bootstrap_tenant.py

frontend/app/mk1-tokens.css
frontend/components/mk1/Mk1AppShell.tsx
frontend/components/mk1/mk1-app-shell.module.css
frontend/lib/mk1-feature-flags.ts
```

The new backend directories are the first incremental modular-monolith
boundaries. No mechanical move of MK0 code was performed.

## Contracts

### Tenant

Every Tenant document has:

```text
tenant_id, name, status, created_at, updated_at
```

The Pydantic model rejects extra fields at the domain boundary.

### TenantContext

```text
tenant_id
actor_id
actor_type = operator | worker | service
```

It is immutable and cannot contain blank authority. HTTP middleware derives it
from verified session subject or the trusted auth-disabled development actor.
Headers, query parameters and bodies are not consulted.

### Tenant-scoped repository

Construction requires a `TenantContext`. Reads always add the context tenant.
Inserts add/verify `tenant_id`. Cross-tenant criteria or documents fail before
Mongo is called. Update operators cannot unset, rename or replace tenant scope;
replacement updates are prohibited.

Explicit migration/admin tooling does not use this adapter and remains isolated
under `application/tenancy/bootstrap.py`.

## Migration behavior

Migration ID: `mk1_s0_bootstrap_tenant_v1`.

1. Resolve the tenant from server configuration.
2. Upsert exactly one Tenant using `$setOnInsert`.
3. Add `tenant_id` only to MK0 records where it is absent in:
   `content_profiles`, `content_runs`, `posts`, `linkedin_connections`.
4. Never overwrite a pre-existing tenant assignment.
5. Verify that no document in the mapped collections remains without scope.

Startup runs this operation after Mongo index creation. A standalone run is:

```bash
cd backend
python -m scripts.migrate_mk1_bootstrap_tenant
```

The command emits counts and a `verified` result. Re-running it is expected to
report zero modifications.

## Feature flags

Backend flags are centrally parsed by `FeatureFlagRegistry`. `MK1_ENABLED=false`
forces all child flags off even if one is accidentally enabled. All defaults are
off, so S0 does not transfer content authority.

The frontend shell scaffold uses `NEXT_PUBLIC_MK1_SHELL=true` only for controlled
preview/development. It remains off by default until dependent MK1 routes exist.

## Application-shell foundation

The frozen Precision Telemetry colors, spacing, radii and motion tokens now exist
under `--pa-*`, including reduced-motion overrides. `Mk1AppShell` encodes the
frozen primary IA and responsive rail/bottom-navigation behavior. It is not the
final screen implementation and is not activated in the normal MK0 build.

## Observability

Bootstrap migration returns per-collection matched/modified/missing counts and a
verification verdict. Startup logs only the non-secret tenant ID and total
modified count. Tenant/actor identifiers are available to later MK1 application
and audit layers through `TenantContext`.

## Failure paths

- invalid explicit bootstrap UUID: startup fails the Mongo-ready path;
- blank deployment key: startup fails the Mongo-ready path;
- Mongo/index/migration failure: database authority remains unavailable rather
  than presenting a partially migrated ready database;
- missing request tenant context: MK1 dependencies return `401`;
- cross-tenant read/write/update: fails locally with `TenantScopeViolation`;
- malformed feature flag: startup fails rather than guessing.

## Risks reviewed

| Risk | S0 response |
|---|---|
| R01 big-bang rewrite | only new boundaries plus small composition/auth hooks; MK0 modules remain |
| R12 cross-tenant leak | structural repository scope, server derivation, negative tests, indexes |
| R13 competing authority | flags default off; mapping metadata does not make MK0 records typed MK1 authority |
| R14 schema-form UX | only tokens/shell foundation; no Profile form introduced |

## Rollback

1. Set `MK1_ENABLED=false` and leave `NEXT_PUBLIC_MK1_SHELL` unset/false.
2. Revert the S0 application commit if code rollback is required.
3. Keep added `tenant_id` fields and indexes: they are additive metadata and do
   not alter MK0 interpretation. Removing them is unnecessary and increases risk.
4. Restore the pre-migration Mongo snapshot only if an independently observed
   data defect requires exact physical rollback.

No destructive rollback script is supplied because the forward migration only
adds isolation metadata and is safe for MK0 readers.

## Tests and evidence

- unit: deterministic tenant ID, fail-closed flags, scoped read/write/update;
- HTTP/security: client tenant header ignored, existing auth/CSRF regression;
- migration: fake-store idempotency plus real-Mongo integration gate;
- MK0 persistence: legacy publication-index regression;
- frontend: frozen IA/token contract, lint, Jest, production build;
- compile: Python module compile.

Canonical results and remaining environment limitations live in
`mk1/test/evidence/S0/CERTIFICATION.md`.

## Known limitations

- S0 provides one bootstrap tenant, not team/RBAC UI.
- MK0 routes remain unscoped legacy authority until their owning slices migrate.
- The MK1 shell is a non-active foundation; later user-facing slices must add
  real routes and desktop/mobile visual certification before activation.
- A live database backup/restore exercise belongs to deployment cutover, not this
  additive S0 development migration.
