# S0 Build Record — Foundation + Bootstrap Tenant

Status: **CERTIFIED — MERGE READY**

Branch: `mk1/s0-foundation-bootstrap-tenant`

Started from: `main@f721c1d1925838b691a443af739d80f7faad7c99`

Initial implementation commit: `69204e331816a6cdf6868946a6ced645b7098095`

Reviewed/hardened code head: `74056ec8930aecd61ad771da94076046dc95a9c8`

Canonical CI for reviewed code: `#677` / run `33892749948` — PASS

## Objective

Install the first MK1 authority boundary without changing MK0 content-generation, approval, scheduling or publication semantics:

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
| `backend/core/auth.py` | signed single-admin session + CSRF | preserve; attach server-derived `TenantContext` after authentication |
| `backend/core/context.py` | generation context has no tenant authority | preserve; MK1 tenant context remains separate |
| `backend/core/container.py` | provider/pipeline composition root | preserve |
| `backend/db/mongo.py` | Mongo connection + legacy indexes | add S0 tenant indexes and bootstrap verification after legacy setup |
| `backend/db/content_runs.py` | direct MK0 ContentRun persistence | preserve untouched; never label it an MK1 repository |
| `backend/models/` | MK0 models | preserve historical semantics |
| `backend/routes/` | legacy direct Mongo paths | preserve until their owning slices transfer authority |
| `frontend/app/` | MK0 IA | preserve as default UI |
| `frontend/lib/api.ts`, `auth.ts` | MK0 clients | preserve |
| `.github/workflows/ci.yml` | Python/Mongo/frontend/browser gates | reuse for real persistence and compatibility evidence |

## New S0 boundaries

```text
backend/domain/tenants/
  models.py
  ports.py

backend/application/tenancy/
  context.py
  bootstrap.py

backend/infrastructure/mongo/
  tenants.py
  scoped_repository.py

backend/core/feature_flags.py
backend/scripts/migrate_mk1_bootstrap_tenant.py

frontend/app/mk1-tokens.css
frontend/components/mk1/Mk1AppShell.tsx
frontend/components/mk1/mk1-app-shell.module.css
frontend/lib/mk1-feature-flags.ts
```

This is incremental modular-monolith convergence; S0 did not mechanically reorganize MK0.

## Contracts implemented

### Tenant

Every Tenant carries:

```text
tenant_id, name, status, created_at, updated_at
```

The domain model rejects extra fields.

### TenantContext

```text
tenant_id
actor_id
actor_type = operator | worker | service
```

It is immutable and cannot contain blank authority. HTTP authority is derived from trusted server identity, never client tenant parameters.

### Tenant-scoped repository

Construction requires a `TenantContext`.

- reads always add current tenant scope;
- inserts add/verify current tenant;
- conflicting tenant criteria/documents fail before persistence;
- replacement updates are prohibited;
- tenant root/nested paths cannot be changed/unset/renamed into.

Migration/admin tooling is deliberately separate from normal business repositories.

## Migration behavior

Migration ID: `mk1_s0_bootstrap_tenant_v1`.

1. Resolve stable tenant identity from server configuration.
2. Upsert one Tenant through `$setOnInsert`.
3. Add `tenant_id` only where absent in `content_profiles`, `content_runs`, `posts`, `linkedin_connections`.
4. Preserve existing non-empty tenant assignments.
5. Count both missing and explicit invalid (`null` / empty) scope.
6. Verification fails closed unless both counts are zero.
7. Re-running a valid migration produces zero modifications.

Standalone verification:

```bash
cd backend
python -m scripts.migrate_mk1_bootstrap_tenant
```

## Review hardening

The required manual tenant-boundary review found and fixed two defects before certification:

1. malformed existing null/empty tenant scope could previously escape the missing-field verification;
2. `$rename` could target a nested `tenant_id.*` destination.

Both were fixed at `74056ec8930aecd61ad771da94076046dc95a9c8` with regression coverage. See `mk1/test/evidence/S0/TENANT_BOUNDARY_REVIEW.md`.

## Feature flags

`FeatureFlagRegistry` parses all MK1 backend flags. `MK1_ENABLED=false` forces all child flags off. Defaults remain off, so S0 transfers no content-generation/publication authority.

`NEXT_PUBLIC_MK1_SHELL=true` is a controlled preview switch only; the shell remains inactive by default.

## Application-shell foundation

Precision Telemetry tokens now exist under `--pa-*`, including reduced-motion handling. `Mk1AppShell` establishes the target navigation/responsive shell boundary without replacing active MK0 user workflows in S0.

## Observability

Bootstrap reports migration ID, tenant ID, matched/modified/missing/invalid counts, completion time and verification verdict. Startup emits a safe bounded summary. Tenant/actor IDs are carried by `TenantContext` for future audit/correlation.

## Failure paths

- invalid explicit bootstrap UUID -> fail Mongo-ready startup path;
- blank deployment key -> fail;
- Mongo/index/migration verification failure -> no persistence readiness;
- missing request tenant context -> `401` for MK1 dependencies;
- cross-tenant query/write/update -> `TenantScopeViolation` before business persistence;
- malformed feature flag -> startup failure rather than guessing.

## Risks reviewed

| Risk | S0 response |
|---|---|
| R01 big-bang rewrite | incremental boundaries only; legacy modules remain |
| R12 cross-tenant leak | structural repository scope + server derivation + adversarial/real-Mongo tests |
| R13 competing authority | MK1 authority flags off; metadata mapping does not reinterpret legacy records |
| R14 schema-form UX | shell/tokens only; no new Profile form |

## Tests / certification

Exact reviewed head `74056ec8930aecd61ad771da94076046dc95a9c8` passed CI `#677` / run `33892749948`:

```text
backend-test       PASS
frontend-test      PASS
UI-01-CERT browser PASS
```

Backend PASS includes full regression, real-Mongo S0 migration/isolation gates, production image build and image smoke. Frontend PASS includes audit/lint/Jest/API-origin gate/build. Browser PASS includes production frontend/backend and desktop/mobile certification.

Canonical detail: `mk1/test/evidence/S0/CERTIFICATION.md`.

## Rollback

1. `MK1_ENABLED=false`.
2. Leave `NEXT_PUBLIC_MK1_SHELL` unset/false.
3. Revert S0 runtime code if required.
4. Normally preserve additive tenant metadata/indexes; deleting isolation metadata increases risk.
5. Restore a database snapshot only for an independently verified physical-data defect.

## Known limitations

- S0 is bootstrap tenancy, not final team/RBAC.
- MK0 routes remain legacy authority until their owning slices migrate.
- the MK1 shell remains inactive until later user-facing slices certify routes/states.
- production backup/restore and production cutover remain separate release gates.

## Slice verdict

S0 implementation, tenant-boundary review and canonical CI satisfy the frozen S0 exit criteria.

**S0: CERTIFIED — MERGE READY.**
