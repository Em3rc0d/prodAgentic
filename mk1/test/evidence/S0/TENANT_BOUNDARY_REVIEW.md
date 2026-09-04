# S0 Tenant Boundary Review

Status: **ACCEPTED**

Reviewed PR: `#35`

Reviewed code head after fixes: `74056ec8930aecd61ad771da94076046dc95a9c8`

Purpose: independently review the S0 multitenant authority boundary before allowing merge. This review is supplemental to automated CI.

## Boundary reviewed

```text
verified/trusted actor
  -> TenantContext
  -> MK1 repository port/adapter
  -> tenant-scoped Mongo predicate/write
```

Also reviewed:

- bootstrap Tenant identity derivation;
- migration of MK0 metadata;
- feature-flag fail-closed behavior;
- startup/readiness integration;
- frontend shell activation boundary;
- real-Mongo isolation tests;
- MK0 authority preservation.

## Confirmed properties

### Authority origin

`tenant_id` is derived server-side. The request client does not choose it through header, query or body. Authenticated requests derive the context from the verified session actor; auth-disabled development/test mode still uses the server-configured admin identity.

### Repository scope

Every new S0 MK1 repository instance requires `TenantContext`. Read/update criteria are augmented with `tenant_id = context.tenant_id`. A conflicting explicit tenant is rejected before the Mongo operation. Inserts enforce the context tenant.

### Tenant immutability

Replacement updates are prohibited through the scoped adapter. Update operators cannot unset/write nested tenant authority or rename another field into `tenant_id` / `tenant_id.*`.

### Migration authority

The bootstrap migration is administrative tooling, deliberately separate from normal scoped repositories. It only fills absent tenant fields and does not reinterpret MK0 records as typed MK1 entities.

Existing non-empty assignments are preserved. Existing null/empty assignments now make verification fail closed for operator review rather than being silently reassigned.

### Feature flags

MK1 authority defaults off. With `MK1_ENABLED=false`, child feature flags are forced off. The frontend MK1 shell is independently inactive by default.

### MK0 coexistence

MK0 repositories/routes remain legacy authority until their owning slices migrate. S0 does not pretend they satisfy the MK1 repository contract; it only adds isolation metadata and the new boundary for future MK1 entities.

## Review findings and fixes

### Finding S0-R01 — migration verified malformed explicit scope

Severity: **BLOCKING before fix**

Original condition:

```text
tenant_id absent -> migrated

tenant_id null/"" -> field exists -> not migrated -> not counted missing -> verified could be true
```

Risk: a legacy business record could remain effectively unscoped while the bootstrap report claimed complete migration.

Resolution in `74056ec8930aecd61ad771da94076046dc95a9c8`:

- add `invalid_after_migration` counts;
- count explicit `null` / empty tenant IDs as invalid;
- `verified` requires missing == 0 AND invalid == 0;
- preserve malformed explicit values for deliberate operator remediation;
- add unit and real-Mongo regressions.

Disposition: **RESOLVED**.

### Finding S0-R02 — `$rename` destination under tenant root

Severity: **BLOCKING before fix**

Original guard rejected direct `tenant_id` update and exact rename destination `tenant_id`, but a destination such as `tenant_id.shadow` was not explicitly rejected.

Risk: an update operator could corrupt the tenant authority root shape.

Resolution in `74056ec8930aecd61ad771da94076046dc95a9c8`:

- inspect `$rename` destination values;
- reject destination `tenant_id` and any `tenant_id.*` path;
- add regression test.

Disposition: **RESOLVED**.

## Adversarial cases checked

- hostile `X-Tenant-ID` header;
- cross-tenant read criteria;
- cross-tenant insert payload;
- tenant `$unset`;
- replacement update;
- `$rename` into tenant authority;
- missing tenant context;
- null/empty legacy tenant assignment;
- valid pre-existing other tenant assignment;
- duplicate/idempotent bootstrap migration;
- multiple repository contexts reading same visible business ID.

## CI revalidation

CI `#677`, run `33892749948`, executed after both review fixes on exact head `74056ec8930aecd61ad771da94076046dc95a9c8`.

```text
backend-test       PASS
frontend-test      PASS
UI browser cert    PASS
```

The backend suite included real-Mongo S0 isolation/migration regressions.

## Non-blocking observations for later slices

- S0 is intentionally a single-bootstrap-tenant foundation, not the final team/RBAC model.
- Each future MK1 repository must compose/meet this tenant-scope contract; direct business Mongo access is not acceptable for new MK1 authority.
- When worker/service identities arrive, their `TenantContext` derivation must be server-side and must not reuse client-provided tenant claims.
- Legacy MK0 write paths must be retired incrementally according to `MIGRATION_FROM_MK0.md`, never by silently treating them as compliant MK1 repositories.

## Verdict

No known blocking tenant-boundary defect remains within S0 scope after the fixes and CI revalidation.

**Tenant boundary review: ACCEPTED.**
