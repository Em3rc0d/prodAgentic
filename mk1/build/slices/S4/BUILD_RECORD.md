# MK1 S4 — VisualSpec V1 — Build Record

Status: **CERTIFIED / MERGED / POST-MERGE GREEN**  
Opened: 2026-09-08  
Closed: 2026-09-08

## Slice

`S4 — VisualSpec V1`

## Entry authority

```text
S3 product certificate
  a10dfec7f5851ae3f8c850fcc934009951f7d422

S4 repository/build entry main
  408f598bae5f200bbd90d9a06883cc740b69bcac
```

No S3 product contract was reopened. S4 consumes certified `ContentSpecV1`, `ContentRevisionV1`, `GenerationRunV1` and `ProfileVersion` lineage.

## Final authority boundary

```text
ContentRevisionV1(DRAFT)
+ accepted ContentSpecV1
+ GenerationRun.VISUAL_PLANNING
+ frozen ProfileVersion
        ↓
DesignProfileV1
        ↓
deterministic S4 visual planner
        ↓
VisualSpecV1
        ↓
copy-ref + structural validation
        ↓
immutable tenant-scoped persistence
        ↓
revision/run visual lineage
        ↓
S5 may later begin RENDERING
```

S4 does **not** render pixels. Chromium/Playwright execution, AssetStore bytes, generated-image provider calls, final asset hashes, pixel QA, approval and publication remain downstream authority.

## Implemented modules

```text
backend/domain/visual/
  __init__.py
  models.py
  ports.py

backend/application/visual/
  __init__.py
  design_profile.py
  planner.py
  validation.py
  service.py

backend/infrastructure/mongo/visual.py
backend/routes/visual.py

backend/tests/
  test_s4_api_surface.py
  test_s4_visualspec.py
  test_mk1_s4_mongo.py

.github/workflows/s4-cert.yml
```

Existing canonical files extended:

```text
backend/main.py       mounts S4 API
backend/db/mongo.py   installs S4 indexes
```

## VisualSpecV1

Certified V1 formats:

```text
single_image
carousel
infographic
```

Strict frozen envelope contains:

```text
visual_spec_id
schema_version = 1
spec_version = 1
content_spec_id
revision_id
format
canvas
render_strategy
visual_pattern
style.design_profile_ref
style.design_profile_digest
pages[]
asset_requirements[]
alt_text_plan
supersedes_visual_spec_id
```

Certified block union:

```text
TextBlockV1
ShapeBlockV1
IconBlockV1
ImageBlockV1
DiagramBlockV1
DividerBlockV1
MetricBlockV1
```

Schemas reject unknown fields, duplicate page/block/asset identities, non-contiguous page indices, invalid safe zones, missing assets and incompatible format/strategy combinations.

## Critical copy authority

Critical editorial copy is owned by accepted `ContentSpecV1`, not VisualSpec.

Critical text requires:

```text
editorial_critical = true
copy_ref != null
literal = null
```

Validated paths include format-specific refs such as:

```text
content_spec.format_spec.headline
content_spec.format_spec.supporting_copy[0]
content_spec.format_spec.slides[slide-2].headline
content_spec.format_spec.slides[slide-2].bullets[1]
content_spec.format_spec.sections[ci].value_or_copy
```

S4 fails closed on unknown refs, wrong-format refs, literal critical text, carousel slide/page mismatch, infographic section mismatch and DesignProfile/content lineage mismatch.

## Format invariants

### Single image

- exactly one 1080×1350 static canvas;
- DesignProfile safe zone;
- accepted headline/supporting copy/footer via critical refs;
- `COMPOSED_STATIC` strategy.

### Carousel

- page count equals accepted slide count;
- slide IDs/order/roles preserved;
- headline/body/bullet refs are exact ID-based refs;
- no extra editorial slide;
- `CAROUSEL` strategy.

### Infographic

- V1 one-canvas layout;
- title and section label/value/relationship use exact refs;
- no fabricated metric/relationship copy;
- `INFOGRAPHIC` strategy.

## DesignProfileV1

S1 persists only `ProfileVersion.visual_system.traits`, so S4 does not mutate upstream history. It derives an immutable policy using mapping version:

```text
mk1-design-profile-v1
```

Derived authority includes controlled typography tokens, palette tokens, density, spacing/radius scales, icon language, image treatment, layout preferences and safe-zone policy.

Rules:

1. same exact ProfileVersion + mapping version => same DesignProfile digest;
2. ProfileVersion digest participates in identity;
3. traits affect only allowlisted semantic buckets;
4. unknown traits cannot inject CSS, font names, URLs, scripts, secrets or renderer directives;
5. mapping changes require a new mapping version.

## Planner decision

S4 V1 uses a deterministic server-owned planner. No external visual-model call occurs in the certified path, so no fake provider attempt evidence is created.

A future model-backed planner must use the same typed boundary plus bounded structured-output repair and persisted attempt evidence before becoming certified authority.

## State boundary

Successful S4 planning leaves:

```text
GenerationRun.state     = VISUAL_PLANNING
ContentRevision.status  = DRAFT
asset_refs              = ()
qa_report_id             = null
```

and binds:

```text
GenerationRun.visual_spec_ref
ContentRevision.visual_spec_ref
ContentRevision.visual_spec_digest
```

S5 owns `VISUAL_PLANNING -> RENDERING` when render execution actually begins.

## Persistence / recovery

Collections:

```text
design_profiles
visual_specs
```

Indexes include tenant-scoped unique DesignProfile and VisualSpec identities plus revision lineage lookup.

Certified recovery rules:

- immutable VisualSpec written before mutable pointer advancement;
- deterministic same-attempt identity makes retry after insert-before-CAS safe;
- `ContentRevision.visual_spec_ref` is the durable S4 pointer;
- if revision CAS survives but the GenerationRun mirror does not, retry validates the referenced spec and repairs the mirror;
- intentional regeneration appends a new VisualSpec with `supersedes_visual_spec_id` instead of overwriting history;
- stale CAS fails closed;
- reads re-verify exact digests;
- no transaction is falsely claimed.

## API

```text
POST /api/content-revisions/{revision_id}/visual-spec
GET  /api/visual-specs/{visual_spec_id}
```

The client cannot submit arbitrary tenant/profile/run/frozen snapshot authority. Server resolution is:

```text
TenantContext
→ ContentRevision
→ GenerationRun
→ persisted ContentSpec artifact
→ exact ProfileVersion
→ derived DesignProfile
```

## Feature gate

Existing frozen flag reused:

```text
MK1_VISUALSPEC
```

It defaults off and remains subordinate to `MK1_ENABLED`. No duplicate flag was introduced.

## Dedicated semantic gate

```text
.github/workflows/s4-cert.yml
job: S4-CERT visualspec-v1
```

The gate proves schemas, copy refs, DesignProfile determinism, Content Seller/Logan/Tech golden fixtures, exact lineage/digests, regeneration history, real Mongo restart, tenant isolation, CAS rejection and absence of renderer/AssetStore/publication execution dependencies.

## Certification chain

Frozen product candidate:

```text
75a0fc048bc172d4a394baf26d44739b3759b3a2
```

Candidate consensus:

```text
backend-test                  PASS
frontend-test                 PASS
UI-01-CERT browser            PASS
DOCKER-COMPOSE-LOCAL smoke    PASS
S3-CERT structured-agent-cell PASS
S4-CERT visualspec-v1         PASS
```

Receipt-only head:

```text
1b056136d3a5a4aa5eec7588555531133dcb0680
```

Receipt-head consensus: **6/6 GREEN**.

Product merge:

```text
PR #46
6a0a653d615e7fa2d1d63bc41b6b265b19646202
```

Post-merge consensus: **6/6 GREEN**.

Canonical evidence receipt:

```text
mk1/test/evidence/S4/CERTIFICATION.md
```

Historical mistakes and near-misses:

```text
mk1/build/slices/S4/ERROR_LEDGER.md
```

## Explicit non-claims

S4 does not certify final image aesthetics, actual render bytes, font fidelity, clipping/overlap, generated-image quality, AssetStore ownership, visual QA, reviewability, approval, scheduling or publication.

## Final decision

```text
S3 product                  CERTIFIED / MERGED
S4 entry main               408f598bae5f200bbd90d9a06883cc740b69bcac
S4 frozen candidate         75a0fc048bc172d4a394baf26d44739b3759b3a2
S4 receipt head             1b056136d3a5a4aa5eec7588555531133dcb0680
S4 product merge            6a0a653d615e7fa2d1d63bc41b6b265b19646202
S4 post-merge consensus     6 / 6 GREEN
S4 certification            CERTIFIED / MERGED
S5 renderer authority       NOT STARTED
```
