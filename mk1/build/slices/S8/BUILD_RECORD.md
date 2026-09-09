# S8 BUILD RECORD — Manual Export Package

Status: IMPLEMENTATION CANDIDATE / CERTIFICATION REQUIRED

## Objective

Make immutable S7 Approval useful even when a destination channel is unsupported, disconnected or intentionally manual, without giving S8 scheduling or publication authority.

## Accepted design authority

- `mk1/plan/VERTICAL_SLICES.md` — S8 Export Package.
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md` — ManualExport is a first-class fallback.
- `mk1/arch/ADR-0008-IMMUTABLE-APPROVAL.md` — ApprovalBundleV2 remains the immutable authority.
- `mk1/plan/RISK_REGISTER.md` — R17 requires asset-byte verification after approval.

## Entry authority

Exact base:

```text
main@9d0c28b19e0985f7a17b7fb8bae0ef30ddc8eddd
```

S7 is certified/merged before this slice starts.

## Authority boundary

```text
immutable ApprovalBundleV2
        ↓ tenant-scoped read
approved ContentRevision + ContentSpec
        ↓ exact digest revalidation
approved AssetV1 metadata
        ↓ fresh AssetStore byte-size + SHA-256 pass #1
ManualExportManifestV1
        ↓ deterministic ZIP projection
fresh AssetStore byte-size + SHA-256 pass #2
        ↓
manifest.json + caption.txt + approved assets
        ↓
ephemeral downloadable ZIP

S9+ outbox / Redis / scheduling / publication: NOT OWNED BY S8
```

The ZIP is never persisted as source of truth. It is a reproducible projection of immutable Approval authority.

## Package contract

`manifest.json` binds:

- Approval ID and exact `ApprovalBundleV2.bundle_sha256`;
- Content ID / Revision ID / ContentSpec ID;
- exact ContentSpec, VisualSpec and QA digests;
- QA policy version;
- exact caption SHA-256;
- ordered approved asset IDs, filenames, byte sizes and SHA-256 values.

`caption.txt` is built only from the exact approved ContentSpec:

```text
hook

body

optional CTA

optional hashtags
```

Approved assets are emitted as deterministic `assets/page-NN.png` names. ZIP entry timestamps, permissions, ordering and compression mode are fixed so equal authority + equal owned bytes produce equal ZIP bytes.

## R17 / race closure

S8 does not trust persisted hashes alone.

Each approved asset is read and hashed once before manifest construction, then read and hashed again while the ZIP is emitted. A missing or changed byte sequence in either pass aborts export. This closes the race in which AssetStore bytes change after manifest creation but before download.

## Secret boundary

The export manifest intentionally excludes:

- authenticated actor identity (`approved_by`);
- OAuth/access tokens;
- provider credentials;
- session/CSRF material;
- runtime environment/configuration;
- repository storage keys.

Only publishable approved content, public-facing asset bytes and immutable integrity metadata are packaged.

## UX

After S7 approval, Review may expose:

- `Download manual package`
- `Create revision`

The export button is shown only when:

- immutable Approval exists; and
- `NEXT_PUBLIC_MK1_MANUAL_EXPORT=true`.

If S8 is rolled back, S7 Review/Approval remains usable and the export action disappears rather than becoming a dead control.

## Failure paths

- missing/wrong-tenant Approval → fail closed;
- revision/content digest drift → fail closed;
- approved asset set/order drift → fail closed;
- missing AssetStore bytes → fail closed;
- byte size/SHA drift on either verification pass → fail closed;
- S8 feature flag disabled → endpoint unavailable;
- no downstream channel capability is required for manual completion.

## Risks touched

- **R17** primary: approved asset bytes can disappear/change; fresh double rehash is the gate.
- **R12**: all reads remain server-tenant scoped and service rechecks tenant lineage.
- **R13**: ZIP is explicitly a projection, never a competing writable source of truth.

## Tests / certification

Dedicated workflow: `.github/workflows/s8-cert.yml`.

Required gates:

1. deterministic ZIP equality for equal authority;
2. manifest/caption/asset hashes bind exact approved content;
3. actor/auth metadata is absent from package bytes;
4. post-approval asset tamper is rejected;
5. change between manifest verification and ZIP emission is rejected;
6. cross-tenant bundle is rejected even under a faulty repository fake;
7. AST boundary proves no S9+ transport/schedule/publication or persistence authority;
8. production frontend build;
9. desktop/mobile Playwright manual fallback action;
10. existing CI, Docker and S3-S7 remain green on the same exact candidate SHA.

## Rollback

Disable backend `MK1_MANUAL_EXPORT` and frontend `NEXT_PUBLIC_MK1_MANUAL_EXPORT`. Existing ApprovalBundleV2 evidence remains valid and unchanged.

## Known limitations

S8 does not queue, schedule, publish, reconcile provider side effects or record publication receipts. Those remain S9/S10 authority.
