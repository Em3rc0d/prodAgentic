# MK1 S4 — VisualSpec V1 — Certification Receipt

Status: **CERTIFIED / MERGED / POST-MERGE GREEN**  
Date: 2026-09-08

## 1. Certificate chain

```text
S4 entry main
408f598bae5f200bbd90d9a06883cc740b69bcac
        ↓
frozen implementation candidate
75a0fc048bc172d4a394baf26d44739b3759b3a2
        ↓ 6/6 exact-candidate consensus
receipt-only head
1b056136d3a5a4aa5eec7588555531133dcb0680
        ↓ 6/6 receipt-head consensus
PR #46 exact-head merge
6a0a653d615e7fa2d1d63bc41b6b265b19646202
        ↓ 6/6 post-merge consensus
S4 PRODUCT CERTIFIED / MERGED
```

S3 product certificate remains an ancestor and independent authority boundary:

```text
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

No S4 product code, test, workflow or contract changed after the frozen candidate. The only pre-merge descendant was this certification receipt.

## 2. Exact-candidate consensus

Frozen candidate:

```text
75a0fc048bc172d4a394baf26d44739b3759b3a2
```

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

Result:

```text
backend-test                  ✅
frontend-test                 ✅
UI-01-CERT browser            ✅
DOCKER-COMPOSE-LOCAL smoke    ✅
S3-CERT structured-agent-cell ✅
S4-CERT visualspec-v1         ✅

6 / 6 GREEN
```

### Frozen candidate artifacts

```text
S4 semantic evidence
artifact 10069991961
sha256   9265f0f3a7f38b416f770c0f9a9f0e2db610259553b0341bc14930e1f115ad0b

S3 regression evidence
artifact 10069993905
sha256   3124fb43fcab3d4a0cff5f48cf874870cc13d41099e101f0ce10516a9781f343

Docker evidence
artifact 10070030609
sha256   7db34b045c9aaf643df62ad31a0207850b148cd5aa672a785ac0c7211bfa9681

UI evidence
artifact 10070117996
sha256   a84b80faf27db66455d720c8a876d422a21c8415cb3ace65185b0afc187f2e22
```

All four artifacts record head SHA `75a0fc048bc172d4a394baf26d44739b3759b3a2`.

## 3. Receipt-head revalidation

Receipt-only head:

```text
1b056136d3a5a4aa5eec7588555531133dcb0680
```

The same six gates passed again without changing S4 product/test/workflow/contract code:

```text
Canonical CI               run 34261879102  ✅ SUCCESS
Docker Compose Local       run 34261879306  ✅ SUCCESS
S3 Structured Agent Cell   run 34261879181  ✅ SUCCESS
S4 VisualSpec V1 Cert      run 34261879142  ✅ SUCCESS
```

Canonical CI included backend, frontend and `UI-01-CERT browser`, producing receipt-head consensus **6/6 GREEN**.

## 4. Exact-head merge

PR:

```text
#46 — MK1 S4: VisualSpec V1
```

Expected merged head:

```text
1b056136d3a5a4aa5eec7588555531133dcb0680
```

GitHub merge result:

```text
merged = true
merge SHA = 6a0a653d615e7fa2d1d63bc41b6b265b19646202
```

The merge did not substitute a different candidate or merge a moved head.

## 5. Post-merge consensus

Exact product merge:

```text
6a0a653d615e7fa2d1d63bc41b6b265b19646202
```

```text
Canonical CI
run 34262319702
frontend-test              SUCCESS
  job 102183080939
backend-test               SUCCESS
  job 102183081078
UI-01-CERT browser         SUCCESS
  job 102183826385

Docker Compose Local
run 34262319658
DOCKER-COMPOSE-LOCAL smoke SUCCESS
  job 102183081385

S3 Structured Agent Cell Cert
run 34262319740
S3-CERT structured-agent-cell SUCCESS
  job 102183081132

S4 VisualSpec V1 Cert
run 34262319707
S4-CERT visualspec-v1      SUCCESS
  job 102183080859
```

Result:

```text
backend-test                  ✅
frontend-test                 ✅
UI-01-CERT browser            ✅
DOCKER-COMPOSE-LOCAL smoke    ✅
S3-CERT structured-agent-cell ✅
S4-CERT visualspec-v1         ✅

POST-MERGE CONSENSUS: 6 / 6 GREEN
```

### Post-merge artifacts

```text
S4 semantic evidence
artifact 10070398745
sha256   8106c7c8d103500aec07701a7f444a1bbd5e9db5891520a77ca3fccb084837d9
head     6a0a653d615e7fa2d1d63bc41b6b265b19646202

S3 regression evidence
artifact 10070399790
sha256   6d9431785ce3eb0bef0cb9cbcd9e38a0df4c2daa3fc924fae9ca4521dd0808d2
head     6a0a653d615e7fa2d1d63bc41b6b265b19646202

Docker evidence
artifact 10070442028
sha256   8e11affc3d32e61b5b57da79ccaf8a3b204ed5bb0f8b3afde02f47f558377ffe
head     6a0a653d615e7fa2d1d63bc41b6b265b19646202

UI evidence
artifact 10070527143
sha256   2290a5127f293a82170838e345895d84338c0c85cfaa30826ce64ac21a8d23cf
head     6a0a653d615e7fa2d1d63bc41b6b265b19646202
```

## 6. Authority proved by S4

S4 certifies this boundary:

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

Certified V1 formats:

```text
single_image
carousel
infographic
```

The semantic gate proves strict page/block schemas, deterministic DesignProfile mapping, Content Seller/Logan/Tech golden fixtures, copy-ref integrity, digest/authority tamper rejection, immutable regeneration lineage, real Mongo restart/reopen behavior, tenant isolation, stale-pointer CAS rejection, fail-closed feature exposure and explicit absence of renderer/AssetStore/publication execution authority.

## 7. Copy authority

Critical editorial copy remains owned by accepted `ContentSpecV1`.

S4 requires critical text blocks to resolve through exact `copy_ref` paths and rejects:

- unknown refs;
- refs outside the actual format union;
- critical literals;
- carousel slide/page mismatch;
- infographic section mismatch;
- DesignProfile ref/digest mismatch;
- content/revision/profile lineage mismatch.

A VisualSpec may use bounded decorative literals only when they are explicitly non-critical.

## 8. DesignProfile authority

`DesignProfileV1` is a deterministic derived policy from the frozen ProfileVersion and mapping version. It does not mutate certified S1 ProfileVersion history.

Free-form visual traits may influence only allowlisted mapping dimensions. They cannot inject arbitrary CSS, fonts, URLs, scripts, secrets or renderer directives.

## 9. Crash/retry semantics

S4 freezes these recovery rules:

1. retry after VisualSpec insert but before revision CAS reuses deterministic immutable intent;
2. `ContentRevision.visual_spec_ref` is the durable S4 pointer;
3. if revision binding survives but the GenerationRun mirror does not, a retry validates exact lineage and repairs the mirror to the same spec;
4. intentional visual regeneration appends a new immutable VisualSpec with `supersedes_visual_spec_id` instead of overwriting history.

No Mongo transaction is falsely claimed.

## 10. State boundary

Successful S4 planning preserves:

```text
GenerationRun.state     = VISUAL_PLANNING
ContentRevision.status  = DRAFT
asset_refs              = ()
qa_report_id             = null
```

S4 does not claim `RENDERING`. S5 owns `VISUAL_PLANNING -> RENDERING` when actual render execution begins.

## 11. Explicit non-claims

S4 does **not** certify:

- final image appearance or pixel quality;
- font loading/render fidelity;
- clipping/overlap;
- Chromium/Playwright render execution;
- image-provider generation quality;
- AssetStore bytes or final asset hashes;
- visual QA verdicts;
- reviewability/approval;
- scheduling or publication.

Those remain S5+ authorities.

## 12. Historical error evidence

The complete S4 engineering trail is retained in:

```text
mk1/build/slices/S4/BUILD_RECORD.md
mk1/build/slices/S4/ERROR_LEDGER.md
```

Known mistakes and near-misses remain part of the certificate and were not deleted after green CI.

## 13. Final declaration

```text
S4 IMPLEMENTATION CANDIDATE   ✅ CERTIFIED
S4 RECEIPT HEAD               ✅ REVALIDATED 6/6
S4 PRODUCT MERGE              ✅ MERGED
S4 POST-MERGE                 ✅ 6/6 GREEN
S4 PRODUCT AUTHORITY          ✅ CERTIFIED / MERGED
S5 RENDERER + ASSETSTORE      ⛔ NOT STARTED
```
