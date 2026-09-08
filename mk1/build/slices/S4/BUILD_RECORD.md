# MK1 S4 — VisualSpec V1 — Build Record

Status: **IMPLEMENTATION ACTIVE — CANDIDATE NOT YET FROZEN**  
Opened: 2026-09-08  
Reconciled after first implementation pass: 2026-09-08

## Slice ID

`S4 — VisualSpec V1`

## Objective

Transfer visual-planning authority from the certified S3 text handoff into a strict, renderer-independent and durable `VisualSpecV1` intermediate representation.

The S4 boundary is:

```text
ContentRevisionV1(DRAFT)
  + accepted ContentSpecV1
  + exact GenerationRun.VISUAL_PLANNING
  + frozen ProfileVersion
        ↓
DesignProfileV1 (deterministic derived policy)
        ↓
S4 deterministic visual planner
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

S4 **does not render**. Chromium rendering, AssetStore bytes, image generation, final asset digests, pixel QA and the transition into actual render execution belong to S5 and later slices.

## Exact entry authority

S3 product certificate:

```text
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

Final S3 documentation descendant:

```text
2dd152e671667e1377907c53748aec83aaf4796b
```

Repository-hygiene / S4 build-entry merge and exact implementation base:

```text
408f598bae5f200bbd90d9a06883cc740b69bcac
```

Active implementation branch:

```text
mk1/s4-visualspec-v1
```

The branch was aligned to that exact `main` SHA before the first S4 source commit.

## Frozen architecture dependencies

S4 remains subordinate to:

- `mk1/arch/VISUAL_SYSTEM.md`;
- `mk1/arch/AGENT_ARCHITECTURE.md`;
- `mk1/arch/CONTRACTS.md`;
- `mk1/arch/DOMAIN_MODEL.md`;
- `mk1/arch/STATE_MACHINES.md`;
- `mk1/arch/INVARIANTS.md`;
- `mk1/arch/GOVERNANCE_QA.md`;
- `mk1/design/DESIGN.md`;
- `mk1/plan/VERTICAL_SLICES.md`;
- `mk1/test/TEST_STRATEGY.md`.

No S3 contract is redefined. S4 consumes the certified `ContentSpecV1`, `ContentRevisionV1`, `GenerationRunV1` and `ProfileVersion` lineage directly.

## V1 supported formats

```text
single_image
carousel
infographic
```

Explicitly outside S4 V1:

```text
text-only VisualSpec generation
GIF
short_video
renderer implementation
Chromium/Playwright rendering
AssetStore writes
image-provider calls
pixel QA
human approval
scheduling
publication
```

A `ContentSpecV1(format="text")` is rejected by the S4 planner as not requiring a VisualSpec.

## Actual implementation map

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

backend/infrastructure/mongo/
  visual.py

backend/routes/
  visual.py

backend/tests/
  test_s4_api_surface.py
  test_s4_visualspec.py
  test_mk1_s4_mongo.py

.github/workflows/
  s4-cert.yml
```

Existing files extended:

```text
backend/main.py       mounts the S4 router
backend/db/mongo.py   installs S4 tenant/lineage indexes
```

No renderer or AssetStore module is created or imported by the S4 authority path.

## VisualSpecV1 contract implemented

`backend/domain/visual/models.py` implements strict frozen models with `extra="forbid"`.

Envelope:

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

V1 block union:

```text
TextBlockV1
ShapeBlockV1
IconBlockV1
ImageBlockV1
DiagramBlockV1
DividerBlockV1
MetricBlockV1
```

Structural gates reject:

- unknown fields;
- duplicate page IDs;
- non-contiguous page indices;
- duplicate block IDs per page;
- duplicate asset requirement IDs;
- ImageBlocks referencing unknown asset requirements;
- incompatible format/render-strategy pairs;
- invalid canvas/safe-zone dimensions.

## Critical-copy authority

Critical editorial copy is never generated inside S4.

A critical `TextBlockV1` must satisfy:

```text
editorial_critical = true
copy_ref != null
literal = null
```

A decorative/non-critical text block may use a bounded literal only when it has exactly one copy source and is explicitly `editorial_critical=false`.

The accepted copy-ref resolver is built from the exact frozen `ContentSpecV1`, not from client-submitted strings.

Examples:

```text
content_spec.format_spec.headline
content_spec.format_spec.supporting_copy[0]
content_spec.format_spec.slides[slide-2].headline
content_spec.format_spec.slides[slide-2].bullets[1]
content_spec.format_spec.sections[ci].value_or_copy
```

S4 validation fails closed on:

- unknown refs;
- refs outside the actual format union;
- ContentSpec identity mismatch;
- missing accepted visual-critical fields;
- carousel page count/order/role mismatch;
- literal critical copy;
- DesignProfile ref/digest/style mismatch.

For V1 the deterministic planner references all accepted format-specific copy that appears in the visual contract rather than silently dropping accepted slide/section content.

## Format invariants implemented

### Single image

- exactly one page;
- static 1080×1350 portrait canvas;
- DesignProfile-derived safe zone;
- accepted headline/supporting copy/footer are critical refs;
- renderer-independent `COMPOSED_STATIC` strategy.

### Carousel

- page count equals exact accepted `CarouselSpecV1.slides` count;
- slide order is preserved;
- page role equals accepted slide role;
- all slide headline/body/bullet refs are exact ID-based refs;
- `CAROUSEL` strategy only;
- no extra editorial slide can be introduced by S4.

### Infographic

- V1 is exactly one canvas;
- accepted title and each section label/value/relationship use exact section-ID refs;
- `INFOGRAPHIC` strategy only;
- no free metric/relationship claim can be fabricated by the planner.

Multi-canvas infographic remains deferred until a later contract version explicitly authorizes it.

## DesignProfileV1

Current S1 `ProfileVersion.visual_system` intentionally remains unchanged and contains only bounded traits. S4 therefore introduces a **derived**, immutable visual policy instead of mutating S1 history.

Mapping version:

```text
mk1-design-profile-v1
```

Derived fields:

```text
design_profile_id
mapping_version
profile_id
profile_version
source_profile_digest
typography token roles
palette token mapping
density
spacing scale
radius scale
icon language
image treatment
layout-family preferences
safe-zone policy
digest
```

Rules implemented:

1. same exact ProfileVersion -> same DesignProfile bytes/digest;
2. the source ProfileVersion digest is part of DesignProfile identity;
3. free-form visual traits are normalized and matched only against an allowlisted vocabulary;
4. unknown traits cannot become CSS, font names, URLs, scripts, token IDs or renderer directives;
5. all emitted style values are controlled enums/token refs;
6. changing the mapping requires a new mapping version;
7. the repository re-verifies the DesignProfile digest on persistence/read.

The initial allowlisted semantic buckets cover sparse/minimal, dense/technical, bold, dark and soft tendencies. Unknown values are ignored as styling instructions while still remaining represented indirectly by the immutable upstream ProfileVersion digest.

## Deterministic planner decision

S4 V1 uses a deterministic server-owned planner rather than a model-backed VisualAgent adapter.

This is deliberate:

- the frozen architecture allows deterministic visual policy;
- S4 does not need provider variance to prove its typed intermediate representation;
- no model means no new provider retry/repair authority is introduced in this slice;
- critical copy remains mechanically derived by reference;
- layout family selection is bounded by DesignProfile preferences.

A future model-backed visual planner may be introduced behind the same typed boundary, but it would require its own bounded structured-output repair and `AgentAttemptEvidenceV1` proof. S4 does not claim that capability now.

## Run-state decision

A successful S4 plan keeps:

```text
GenerationRun.state = VISUAL_PLANNING
ContentRevision.status = DRAFT
```

and binds only:

```text
GenerationRun.visual_spec_ref
ContentRevision.visual_spec_ref
ContentRevision.visual_spec_digest
```

Reason: `RENDERING` means render execution has actually begun. S4 must not fabricate an S5 state transition merely because visual intent exists.

S5 owns the future transition:

```text
VISUAL_PLANNING -> RENDERING
```

## Persistence / crash recovery

Collections:

```text
design_profiles
visual_specs
```

Indexes:

```text
(tenant_id, design_profile_id) UNIQUE
(tenant_id, profile_id, profile_version, mapping_version) UNIQUE
(tenant_id, visual_spec_id) UNIQUE
(tenant_id, revision_id, created_at)
```

Persistence properties:

- tenant scope is structural through `TenantScopedMongoRepository`;
- DesignProfile and VisualSpec snapshots are immutable business/evidence records;
- exact hashes are verified on read;
- revision pointer advance uses compare-and-set;
- regeneration appends a new VisualSpec and sets `supersedes_visual_spec_id` rather than overwriting history;
- exact visual-plan identity is deterministic for the same revision/content/design/previous-pointer planning attempt;
- retry after a crash between spec insert and revision CAS reuses the same immutable VisualSpec ID;
- `ContentRevision.visual_spec_ref` is the durable S4 pointer;
- if a process dies after revision CAS but before the `GenerationRun.visual_spec_ref` mirror update, the next call verifies the lineage, repairs the run mirror and returns the already-bound spec instead of producing a second accidental regeneration.

No transaction is falsely claimed. Recovery semantics are explicit and tested.

## API boundary implemented

```text
POST /api/content-revisions/{revision_id}/visual-spec
GET  /api/visual-specs/{visual_spec_id}
```

The POST body carries no tenant/profile/run/frozen snapshot authority. The server resolves:

```text
TenantContext
-> ContentRevision
-> GenerationRun
-> persisted ContentSpec artifact
-> exact ProfileVersion
-> derived DesignProfile
```

The GET path re-verifies VisualSpec and DesignProfile integrity before returning them.

## Feature gate

S4 reuses the already-frozen flag:

```text
MK1_VISUALSPEC
```

It remains subordinate to `MK1_ENABLED` and defaults off. No second S4 flag was invented.

S4-CERT explicitly runs with:

```text
MK1_VISUALSPEC=true
MK1_RENDER_WORKER=false
IMAGE_RENDER_ENABLED=false
SCHEDULER_ENABLED=false
```

## Dedicated certification workflow

Workflow:

```text
.github/workflows/s4-cert.yml
```

Job:

```text
S4-CERT visualspec-v1
```

The dedicated gate proves:

- S4 modules compile;
- canonical API surface is mounted;
- feature flag is fail-closed and master-gated;
- strict VisualSpec contract behavior;
- deterministic DesignProfile mapping;
- Content Seller single-image golden fixture;
- Logan/automotive carousel golden fixture;
- Tech/LinkedIn infographic golden fixture;
- copy-ref resolution/integrity and missing-copy rejection;
- exact lineage/digest authority;
- immutable regeneration lineage;
- real Mongo restart/reopen behavior;
- tenant isolation;
- stale revision-pointer CAS rejection;
- zero AssetStore/publication side effects in the S4 Mongo scenario;
- AST source probe for renderer/AssetStore/publication execution dependency.

## Required exact-candidate consensus

One immutable S4 candidate SHA must pass unchanged:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
S3-CERT structured-agent-cell
S4-CERT visualspec-v1
```

Only after all six pass may the implementation SHA be frozen as the S4 candidate.

Then a receipt-only documentation head may record the evidence. That exact receipt head must pass all six gates again before exact-head merge. The merged `main` SHA must then pass post-merge consensus.

## Golden fixtures

S4 semantic/layout golden coverage is intentionally cross-product:

```text
Content Seller       single_image
Logan / automotive   carousel
Tech / LinkedIn      infographic
```

The golden output is a stable semantic/layout IR, **not pixels**.

## Explicit non-claims

S4 does not certify:

- final image appearance;
- font loading/render fidelity;
- clipping/overlap;
- image-generation quality;
- actual asset bytes;
- AssetStore ownership;
- visual model QA;
- publication readiness;
- human approval.

Those remain downstream gates.

## Candidate-freeze law

Before freezing a candidate:

1. reconcile this record with actual code;
2. append every discovered error/near-miss to `ERROR_LEDGER.md`;
3. inspect the full branch diff against `408f598...`;
4. obtain S4-specific tests plus normal regressions;
5. leave no unresolved architecture/product decision inside S4.

After candidate freeze, no product/test/workflow/contract change is allowed. Only certification receipts may be appended, and those create a new receipt head requiring full revalidation.

## Current decision

```text
S3 product                  CERTIFIED / MERGED
S4 entry main               408f598bae5f200bbd90d9a06883cc740b69bcac
S4 branch                   ALIGNED / ACTIVE
VisualSpecV1                IMPLEMENTED
DesignProfileV1             IMPLEMENTED
copy-ref integrity          IMPLEMENTED
Mongo persistence           IMPLEMENTED
S4-CERT workflow            IMPLEMENTED
S4 candidate                NOT FROZEN
S4 certification            NOT CLAIMED
S5 renderer authority       NOT STARTED
```
