# MK1 S4 — VisualSpec V1 — Build Record

Status: **BUILD ENTRY OPEN — IMPLEMENTATION NOT YET CERTIFIED**  
Opened: 2026-09-08

## Slice ID

`S4 — VisualSpec V1`

## Objective

Transfer visual-planning authority from the frozen S3 text handoff into a typed, renderer-independent `VisualSpecV1` intermediate representation.

S4 must stop before render execution. The certified boundary is:

```text
ContentRevisionV1(DRAFT)
  + accepted ContentSpecV1
  + frozen ProfileVersion.visual_system
  + platform/canvas capability
        ↓
VisualAgent / deterministic visual policy
        ↓
VisualSpecV1
        ↓
GenerationRun remains ready for S5 render authority
```

S5 owns Chromium rendering, AssetStore bytes, asset hashes and preview bytes. S4 must not claim those capabilities.

## Entry authority

S3 product certificate:

```text
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

S3 documentation closure / pre-S4 `main`:

```text
2dd152e671667e1377907c53748aec83aaf4796b
```

The S4 implementation branch must be aligned to the final repository-hygiene/S4-entry `main` before source changes begin.

Active branch name:

```text
mk1/s4-visualspec-v1
```

## Frozen accepted design dependencies

S4 implementation is subordinate to:

- `mk1/arch/VISUAL_SYSTEM.md` — VisualSpec envelope, page/block model, render strategies and DesignProfile concept;
- `mk1/arch/AGENT_ARCHITECTURE.md` — VisualAgent authority, inputs, output and model-routing evidence;
- `mk1/arch/CONTRACTS.md` — accepted structured-contract family;
- `mk1/arch/DOMAIN_MODEL.md` — revision/run ownership and aggregate boundaries;
- `mk1/arch/STATE_MACHINES.md` — GenerationRun/ContentItem lifecycle;
- `mk1/arch/INVARIANTS.md` — authority and immutability rules;
- `mk1/arch/GOVERNANCE_QA.md` — visual failure/recovery boundaries;
- `mk1/design/DESIGN.md` and accepted product design docs — visual signature and low-friction UX constraints;
- `mk1/plan/VERTICAL_SLICES.md` — S4 exit criteria;
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md` — implementation scope;
- `mk1/test/TEST_STRATEGY.md` and golden datasets — certification requirements.

## Frozen S4 scope

V1 supported visual formats:

```text
single_image
carousel
infographic
```

Explicitly out of scope:

```text
text-only visual generation
GIF
short_video
renderer implementation
AssetStore bytes
visual QA/recovery
human approval
publication/scheduling
```

A text-only ContentSpec does not require a VisualSpec unless a later policy explicitly promotes it through a separate accepted contract.

## Existing runtime inspected at entry

### S3 typed production boundary

`backend/domain/production/models.py` already provides:

- `ContentSpecV1`;
- `SingleImageSpecV1`;
- `CarouselSpecV1` / `CarouselSlideV1`;
- `InfographicSpecV1` / `InfographicSectionV1`;
- `ContentRevisionV1`;
- `GenerationRunV1` with `VISUAL_PLANNING` state;
- `AgentKind.VISUAL` and typed attempt evidence.

This is the authoritative S4 input lineage. S4 must not create a second competing ContentSpec family.

### Profile visual input

`ProfileVersion` contains:

```text
visual_system: VisualSystem
```

and the current `VisualSystem` contract contains:

```text
traits: tuple[str, ...]
```

The architecture describes a richer DesignProfile policy (typography roles, palette mapping, density, spacing/radius, icon language, image treatment, layout preferences and marks), but those fields are not currently first-class mutable ProfileVersion fields.

S4 therefore must introduce a **deterministic derived DesignProfile mapping** from the immutable ProfileVersion snapshot/traits plus controlled defaults/presets. It must not silently mutate S1 ProfileVersion schema or invent user brand properties that were never accepted.

### Legacy/MK0 visual capability

Historical visual/rendering code is evidence and potential adapter material only. It does not become MK1 S4 authority by name. In particular, prior raw prompt/image-generation or renderer-specific objects cannot bypass `VisualSpecV1`.

## Proposed module boundary

Target layout, subject to code inspection before first source commit:

```text
backend/domain/visual/
  __init__.py
  models.py              # VisualSpecV1, page/block unions, asset requirements, DesignProfileV1
  ports.py               # VisualPlannerPort / VisualAgentPort

backend/application/visual/
  __init__.py
  design_profile.py      # deterministic ProfileVersion -> DesignProfileV1
  service.py             # authority checks + VisualSpec production/persistence
  validation.py          # copy-ref, page-count and structural invariants

backend/infrastructure/agents/
  structured_visual.py   # model-backed typed VisualAgent adapter, if needed

backend/infrastructure/mongo/
  visual.py              # tenant-scoped VisualSpec lineage persistence

backend/routes/
  visual.py              # bounded S4 planning/read surface

backend/tests/
  test_s4_visual_contracts.py
  test_s4_copy_reference_integrity.py
  test_s4_design_profile_mapping.py
  test_s4_visual_service.py
  test_s4_structured_visual_adapter.py
  test_mk1_s4_mongo.py
```

Do not create renderer/asset modules under S4 merely as placeholders for S5 unless interfaces are strictly necessary for capability input.

## VisualSpecV1 authority

The implementation must conform to the frozen envelope:

```text
visual_spec_id
spec_version = 1
content_spec_id
revision_id
format = single_image | carousel | infographic
canvas
render_strategy
visual_pattern
style.design_profile_ref
pages[]
asset_requirements[]
alt_text_plan
```

Page/block structure must be typed, bounded and reject unknown fields.

Allowed V1 block union:

```text
TextBlock
ShapeBlock
IconBlock
ImageBlock
DiagramBlock
DividerBlock
MetricBlock
```

## Critical-copy rule

Critical editorial text is owned by the accepted `ContentSpecV1`, not by VisualAgent.

VisualSpec critical `TextBlock` values must use validated `copy_ref` paths such as:

```text
content_spec.format_spec.slides[slide-2].headline
```

Literal text is permitted only for bounded decorative microcopy with:

```text
editorial_critical = false
```

S4 validation must fail closed on:

- unknown copy refs;
- refs to a different ContentSpec;
- refs whose format path is invalid for the actual format union;
- duplicate/ambiguous page or block IDs;
- missing critical hook/headline coverage required by format policy;
- literal critical text where a copy reference is required.

## Format-specific invariants

### Single image

- exactly one page;
- canvas within accepted static bounds;
- hook/headline represented by a critical copy ref;
- supporting copy references accepted ContentSpec values when editorially critical;
- render strategy must be compatible with a single canvas.

### Carousel

- page count must correspond to accepted carousel semantics and configured bounds;
- page indices contiguous and unique;
- each page has a stable role/layout family;
- critical headlines/bodies reference the exact slide IDs from ContentSpec;
- no VisualAgent-created extra editorial slide is allowed.

### Infographic

- one or bounded multi-canvas spec only if frozen contract permits it;
- title/sections reference exact infographic title/section IDs;
- metric blocks cannot fabricate numbers; any metric content must resolve from ContentSpec/research authority through a copy ref;
- relationship/diagram semantics cannot add unsupported factual claims.

## DesignProfileV1 mapping

S4 must create an immutable, digestible derived visual policy with at least:

```text
design_profile_id / version or stable digest
profile_id
profile_version
source_profile_digest
typography roles/preset IDs
palette token mapping
density
spacing/radius scale
icon language
image treatment
layout-family preferences
safe-zone policy
```

Rules:

1. mapping is deterministic for the same ProfileVersion + mapping version;
2. unknown/free-form traits may influence only allowlisted mapping dimensions;
3. no arbitrary CSS/font/url/script is accepted from Profile traits;
4. output is versioned/digestible and suitable for snapshot tests;
5. S4 does not distribute font files or embed secret/external auth material;
6. mapping changes require a new mapping version and invalidate affected visual specs according to dependency rules.

## Render-strategy policy

V1 strategies remain those frozen by architecture:

```text
COMPOSED_STATIC
GENERATED_BACKGROUND
GENERATED_VISUAL_PLUS_COMPOSITE
DIAGRAM
CAROUSEL
INFOGRAPHIC
PHOTO_OVERLAY
```

S4 chooses/specifies strategy but does not render it.

Strategy selection must be deterministic where the format/content semantics are deterministic. A model may propose visual semantics inside a bounded contract, but server policy owns final compatibility validation.

## Persistence and lineage

VisualSpec is durable business/evidence state, not ephemeral model output.

Required persistence properties:

- `tenant_id` scoped;
- exact `content_spec_id` + `revision_id` binding;
- exact ProfileVersion/design-profile digest binding;
- immutable spec snapshot once accepted by S4;
- regeneration creates a new VisualSpec lineage item rather than overwriting history;
- provider/model attempt evidence, when a model is used, follows the S3 AgentAttempt evidence discipline;
- process restart can reopen/read the exact VisualSpec.

A successful S4 handoff must not mark the content `REVIEWABLE`, `APPROVED` or `COMPLETED`.

## API boundary

Expected bounded API shape, to be finalized during implementation without leaking raw schemas into the UX:

```text
POST /api/content-revisions/{revision_id}/visual-spec
GET  /api/visual-specs/{visual_spec_id}
```

The server must resolve tenant, revision, ContentSpec, ProfileVersion and GenerationRun authority. The client may not submit arbitrary frozen snapshots or choose another tenant/profile/run.

If existing routing conventions require a different resource path, the build record must document the decision before candidate freeze.

## Feature gate

Before adding a new flag, inspect the frozen registry. If an S4-specific flag already exists, reuse it. Otherwise introduce one narrow fail-closed flag subordinate to `MK1_ENABLED`.

S4 must default off until certified.

## Required certification gates

Canonical regression gates remain mandatory on one exact candidate SHA:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
```

S4 adds a dedicated semantic gate:

```text
S4-CERT visualspec-v1
```

The dedicated gate must cover at minimum:

- strict VisualSpec/page/block schema validation;
- single-image/carousel/infographic fixtures;
- copy-ref resolution and rejection of unknown/critical literals;
- deterministic DesignProfile mapping snapshots;
- format/page-count/canvas/layout compatibility;
- asset requirement structural validation without rendering;
- tenant/revision/content/profile lineage binding;
- restart/reopen persistence;
- bounded model structured-output repair if model-backed planning is enabled;
- feature flag fail-closed behavior;
- explicit proof that no renderer/AssetStore/publication side effect occurs.

## Golden fixtures

At least the three product lines already named by MK1 architecture should be represented:

```text
Content Seller
Logan / automotive
Tech / LinkedIn
```

For S4 the golden result is the stable semantic/layout spec, not pixel rendering. Pixel quality is S5 authority.

## Risks touched

S4 directly touches visual-quality risk R07 and introduces several implementation risks:

- visually valid but generic/unbranded specs;
- free-form Profile visual traits leaking arbitrary styling authority;
- model-generated critical text bypassing ContentSpec;
- carousel page mismatch vs accepted slide IDs;
- metric/diagram blocks accidentally increasing factual specificity;
- renderer concerns leaking backward into the domain IR;
- unstable layout mappings causing non-reproducible snapshots;
- S4 overclaiming S5 render quality.

Mitigations are encoded in the typed contract, deterministic DesignProfile mapping, copy refs, strict strategy/format policy and explicit S5 boundary.

## Candidate freeze law

Before candidate freeze:

1. reconcile this build record with actual modules/endpoints;
2. append every discovered mistake/near-miss to `ERROR_LEDGER.md`;
3. ensure docs/status are truthful;
4. run implementation-specific preflight tests;
5. make no remaining architecture/product decisions.

Then freeze one exact implementation SHA. After freeze, no product/test/workflow/contract change is allowed. A receipt-only documentation head may follow only after the exact candidate is fully green.

## Exit claim

S4 may be declared `CERTIFIED / MERGED` only when it proves:

```text
accepted ContentSpec + exact revision/profile authority
        ↓
strict VisualSpecV1
        ↓
validated critical copy refs
        ↓
deterministic DesignProfile mapping
        ↓
durable restart-safe lineage
```

with no rendering claim.

## Current decision

```text
S3 product                  CERTIFIED / MERGED
S3 docs                     CLOSED
Repository hygiene          IN ENTRY RECONCILIATION
S4 branch                   CREATED, MUST ALIGN TO FINAL ENTRY MAIN
S4 implementation           NOT STARTED
S4 candidate                NOT FROZEN
S4 certification            NOT CLAIMED
S5 renderer authority       NOT STARTED
```
