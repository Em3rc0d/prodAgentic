# MK1 S4 — VisualSpec V1 — Certification Receipt

Status: **CANDIDATE CERTIFIED — RECEIPT HEAD REVALIDATION PENDING**  
Date: 2026-09-08

## 1. Certified implementation candidate

The S4 product/test/workflow/contract candidate is frozen at:

```text
75a0fc048bc172d4a394baf26d44739b3759b3a2
```

Entry authority:

```text
S4 entry main
408f598bae5f200bbd90d9a06883cc740b69bcac

S3 product certificate ancestor
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

After this candidate freeze, no S4 product code, test, workflow or contract change is permitted under this certificate. This file is a receipt-only descendant and therefore creates a new PR head that must itself be fully revalidated before merge.

## 2. Exact-candidate consensus

All required gates passed on the exact candidate SHA `75a0fc048bc172d4a394baf26d44739b3759b3a2`.

```text
Canonical CI
run 34261298767
frontend-test              SUCCESS
  job 102179622165
backend-test               SUCCESS
  job 102179622340
UI-01-CERT browser         SUCCESS
  job 102180286801

Docker Compose Local
run 34261298665
DOCKER-COMPOSE-LOCAL smoke SUCCESS
  job 102179621834

S3 Structured Agent Cell Cert
run 34261298673
S3-CERT structured-agent-cell SUCCESS

S4 VisualSpec V1 Cert
run 34261298754
S4-CERT visualspec-v1      SUCCESS
  job 102179622235
```

Consensus:

```text
backend-test                  ✅
frontend-test                 ✅
UI-01-CERT browser            ✅
DOCKER-COMPOSE-LOCAL smoke    ✅
S3-CERT structured-agent-cell ✅
S4-CERT visualspec-v1         ✅

6 / 6 GREEN
```

## 3. Frozen evidence artifacts

### S4 semantic certificate

```text
artifact id   10069991961
name          s4-visualspec-v1-evidence
sha256        9265f0f3a7f38b416f770c0f9a9f0e2db610259553b0341bc14930e1f115ad0b
run           34261298754
head          75a0fc048bc172d4a394baf26d44739b3759b3a2
```

### S3 regression certificate

```text
artifact id   10069993905
name          s3-structured-agent-cell-evidence
sha256        3124fb43fcab3d4a0cff5f48cf874870cc13d41099e101f0ce10516a9781f343
run           34261298673
head          75a0fc048bc172d4a394baf26d44739b3759b3a2
```

### Docker local-stack evidence

```text
artifact id   10070030609
name          docker-compose-local-evidence
sha256        7db34b045c9aaf643df62ad31a0207850b148cd5aa672a785ac0c7211bfa9681
run           34261298665
head          75a0fc048bc172d4a394baf26d44739b3759b3a2
```

### Browser evidence

```text
artifact id   10070117996
name          ui-01-cert-evidence
sha256        a84b80faf27db66455d720c8a876d422a21c8415cb3ace65185b0afc187f2e22
run           34261298767
head          75a0fc048bc172d4a394baf26d44739b3759b3a2
```

## 4. Authority proved by S4

The candidate proves the following S4 boundary:

```text
accepted ContentSpecV1
+ exact DRAFT ContentRevisionV1
+ GenerationRun.VISUAL_PLANNING
+ exact frozen ProfileVersion
        ↓
deterministic DesignProfileV1
        ↓
strict VisualSpecV1
        ↓
validated critical copy_refs
        ↓
tenant-scoped immutable persistence
        ↓
restart-safe revision/run visual lineage
```

The certified V1 visual formats are:

```text
single_image
carousel
infographic
```

The S4 semantic gate covers strict page/block schemas, deterministic DesignProfile mapping, cross-product golden fixtures, copy-reference integrity, digest/authority tamper rejection, immutable regeneration lineage, Mongo restart/reopen behavior, tenant isolation, stale-pointer CAS rejection, fail-closed feature exposure and explicit absence of renderer/AssetStore/publication execution authority.

## 5. Crash/retry semantics frozen

S4 persists immutable visual intent before advancing mutable pointers. The certified recovery rules are:

1. retry after VisualSpec insert but before revision CAS reuses deterministic immutable intent rather than replacing history;
2. `ContentRevision.visual_spec_ref` is the durable S4 pointer;
3. if revision binding survives but the GenerationRun mirror does not, a retry verifies exact lineage and repairs `GenerationRun.visual_spec_ref` to the same spec;
4. regeneration after an already-bound spec creates a new lineage item with `supersedes_visual_spec_id`; it does not overwrite the prior spec.

No Mongo transaction is falsely claimed.

## 6. State boundary frozen

Successful S4 planning preserves:

```text
GenerationRun.state     = VISUAL_PLANNING
ContentRevision.status  = DRAFT
asset_refs              = ()
qa_report_id             = null
```

S4 does not transition to `RENDERING`. S5 owns that transition when render execution actually starts.

## 7. Explicit non-claims

This certificate does **not** certify:

- final pixels or image aesthetics;
- font loading/render fidelity;
- clipping/overlap checks;
- Chromium/Playwright rendering;
- image-provider generation quality;
- AssetStore bytes or final asset SHA-256;
- visual QA verdicts;
- reviewability/approval;
- scheduling or publication.

Those are downstream S5+ authorities.

## 8. Error-ledger continuity

S4 build history and near-misses remain preserved in:

```text
mk1/build/slices/S4/BUILD_RECORD.md
mk1/build/slices/S4/ERROR_LEDGER.md
```

The ledger includes repository-entry mistakes, upstream visual-profile mismatch, legacy-authority risk, stale repository state, S4/S5 overclaim risk, crash windows, durable-pointer recovery, GenerationRun state-boundary handling and the deterministic-planner evidence decision. Entries are not erased because the candidate became green.

## 9. Remaining certification sequence

This receipt is not itself the merge certificate yet.

Required next steps:

```text
receipt-only HEAD
    ↓
all six gates on exact receipt HEAD
    ↓
PR ready
    ↓
merge with expected exact receipt HEAD
    ↓
main@MERGE_SHA
    ↓
all six gates post-merge
    ↓
final documentation closure
    ↓
S4 CERTIFIED / MERGED
```

Until that sequence closes, the authoritative status is:

```text
S4 IMPLEMENTATION CANDIDATE   ✅ CERTIFIED
S4 PRODUCT MERGE              ⏳ PENDING
S4 FINAL CERTIFICATE          ⏳ PENDING
S5                            ⛔ NOT STARTED
```
