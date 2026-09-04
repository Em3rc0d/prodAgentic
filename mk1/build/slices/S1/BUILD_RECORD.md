# S1 Build Record — Profile V2

Status: **IMPLEMENTED — CERTIFICATION IN PROGRESS**

Branch: `mk1/s1-profile-v2`

Started from: `main@88a615c519b5918944256afd678b67139ed8f0bd`

Implementation commit: `47b4d20e5e43f18516b7c25a604165542317d291`

## Objective

Transfer new Profile creation and update authority into the MK1
`Profile`/immutable `ProfileVersion` model without rewriting MK0 history or
turning setup into a backend-schema form.

```text
quick setup
  -> deterministic inference proposal
  -> explicit human acceptance
  -> Profile pointer + immutable ProfileVersion
  -> frozen snapshot read
```

## Accepted authority

- `mk1/design/PROFILE_SETUP.md`
- `mk1/arch/DOMAIN_MODEL.md` — Profile and ProfileVersion
- `mk1/arch/INVARIANTS.md` — invariants 1–5
- `mk1/arch/DATA_ARCHITECTURE.md` — profile snapshot/index rules
- `mk1/build/MIGRATION_FROM_MK0.md` — Stage 2
- `mk1/plan/VERTICAL_SLICES.md` — S1
- `mk1/test/ACCEPTANCE_SCENARIOS.md` — AS-01, AS-11, AS-14

No accepted contract or ADR change is currently required.

## MK0 implementation map inspected

| Area | MK0 behavior | S1 treatment |
|---|---|---|
| `backend/models/content_profile.py` | one mutable profile document with incremented version | preserve for MK0; bridge through an explicit allowlist adapter |
| `backend/routes/content_profiles.py` | direct unversioned legacy Mongo CRUD | preserve under `/content-profiles`; new MK1 API is separate and feature-gated |
| `backend/db/content_runs.py` | embeds legacy ContentProfile snapshot | preserve historical behavior; S2/S3 will consume the new frozen snapshot contract |
| `frontend/app/profiles/` | large configuration editor mirroring backend fields | preserve when S1 flag is off; replace with quick setup when explicitly enabled |
| `frontend/lib/api.ts` | MK0 ContentProfile client | preserve; add separate typed MK1 Profile client |

## Contracts fixed before runtime work

- `Profile` is the mutable stable pointer and carries `tenant_id`.
- `ProfileVersion` is an extra-forbid, immutable snapshot with canonical SHA-256 digest.
- updates require `expected_current_version`; stale updates fail with conflict.
- inference is a proposal with evidence/confidence, never hidden authority.
- acceptance recomputes and verifies the proposal digest server-side.
- examples are represented in snapshots by type, digest and bounded metadata, not raw secrets.
- recursive secret-field rejection covers setup, bridge and persisted snapshots.
- connections/OAuth material remain separate tenant-owned resources.

## Migration behavior

Migration ID: `mk1_s1_profile_bridge_v1`.

The bridge reads only bootstrap-tenant MK0 `content_profiles`, maps an explicit
allowlist into ProfileVersion V2, records source version/digest provenance, and
uses idempotent tenant/profile/version keys. It never mutates or deletes MK0
profiles and never imports token/credential/secret fields.

## Feature flags and authority

- backend requires both `MK1_ENABLED=true` and `MK1_PROFILE_V2=true`;
- frontend requires `NEXT_PUBLIC_MK1_SHELL=true` and
  `NEXT_PUBLIC_MK1_PROFILE_V2=true`;
- defaults remain off;
- MK0 `/content-profiles` behavior remains available during the bridge window.

## Risks reviewed

| Risk | S1 control |
|---|---|
| R01 big-bang rewrite | additive API, collections and UI gate; MK0 path remains |
| R12 cross-tenant leak | S0 scoped repositories + negative API/repository tests |
| R13 competing authority | distinct routes/flags; bridge is read-only over MK0 and idempotent into MK1 |
| R14 schema-form UX | six-step quick setup, optional examples, proposal confirmation, progressive disclosure |

## Failure paths

- disabled feature returns a bounded not-found response;
- stale version update returns conflict and does not create/advance authority;
- proposal digest mismatch fails acceptance;
- invalid/secret-shaped input fails before persistence;
- partial version/pointer write is compensated before returning failure;
- malformed MK0 records are reported and skipped/fail verification rather than guessed.

## Observability

Application results carry tenant/profile/version/digest and proposal evidence
counts. Migration reports scanned/migrated/existing/invalid counts without raw
examples or secrets.

## Rollback

Disable both S1 feature flags. MK0 remains authoritative. New additive
`profiles`/`profile_versions` documents may remain for audit; destructive removal
is not required. Exact physical rollback uses a verified database snapshot only
when independently justified.

## Required certification

- domain/contract/hash and secret-rejection tests;
- proposal determinism and explicit-acceptance tests;
- immutable history and stale-update tests;
- cross-tenant API/repository matrix;
- bridge allowlist/idempotency/real-Mongo tests;
- MK0 full regression;
- frontend unit, lint and production build;
- desktop/mobile quick-setup browser certification;
- build/certification records with immutable CI evidence.

## Known limitations

- S1 creates editorial Profiles, not team/RBAC management.
- imported examples are text/bio only; asset/link ingestion adapters remain later capabilities.
- S1 does not rebase existing Batches because MK1 Batch authority begins in S2.
- OAuth connection selection is editorial preference only; actual credentials remain outside Profile.
