# S5 — Renderer + AssetStore — Build Record

Status: **BUILD COMPLETE / CERTIFICATION CANDIDATE NOT YET FROZEN**

Entry authority:

```text
main@abae59fd9815d27a4fb6e3caaeac953618dd3364
S4 product certificate: 6a0a653d615e7fa2d1d63bc41b6b265b19646202
branch: mk1/s5-renderer-assetstore
```

## Objective

Convert the certified immutable S4 visual intent into product-owned render bytes without transferring editorial authority to the renderer.

Canonical implemented flow:

```text
exact ContentSpecV1
+ exact ContentRevisionV1
+ certified VisualSpecV1
+ exact DesignProfileV1
        ↓
resolved RendererRequestV1
        ↓
ChromiumRendererAdapter
        ↓
isolated Playwright/Chromium sidecar
        ↓
FilesystemAssetStore
        ↓
owned PNG bytes + read-back SHA-256
        ↓
AssetV1[] + RenderResultV1
        ↓
CAS bind exact asset set
        ↓
ContentRevision.QA_PENDING
GenerationRun.QA
        ↓
read-only Review preview
```

S5 does not claim semantic/visual QA success. It performs only render-integrity checks necessary to prove the owned output: exact page identity/count, actual PNG dimensions, storage existence, metadata lineage and digest integrity. S6 owns QA and the transition to `REVIEWABLE`.

## Accepted design / ADR dependencies

- `mk1/plan/VERTICAL_SLICES.md` — S5 Renderer + AssetStore exit criteria.
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md` — exact dimensions/page count, durable root, hash vectors, golden renders, desktop/mobile preview and recoverable renderer failures.
- `mk1/arch/VISUAL_SYSTEM.md` — typed VisualSpec → RendererPort → Chromium/Playwright → AssetStore.
- `mk1/arch/DATA_ARCHITECTURE.md` — Mongo state + product-owned filesystem-first AssetStore rooted at `PRODAGENTIC_ASSET_ROOT`.
- `mk1/arch/STATE_MACHINES.md` — `VISUAL_PLANNING → RENDERING → QA` and `DRAFT → QA_PENDING`.
- `mk1/arch/adr/ADR-0012-CHROMIUM-RENDERER.md` — Chromium/Playwright is the first renderer adapter.
- `mk1/design/REVIEW.md` — S5 preview is not approval authority.
- `mk1/test/GOLDEN_DATASETS.md` — Content Seller / Logan / Tech visual golden lines.

## Certified upstream authority consumed

S5 consumes without rewriting the S3/S4 product boundary:

- `ContentSpecV1`, `ContentRevisionV1`, `GenerationRunV1`;
- `DesignProfileV1`, `VisualSpecV1` and S4 copy-ref validation;
- exact persisted ContentSpec/VisualSpec/Profile digests;
- `GenerationRun.VISUAL_PLANNING` and `ContentRevision.DRAFT` as render-entry authority.

No S4 renderer execution was retrofitted into S4.

## Runtime modules introduced

```text
backend/domain/rendering/
  __init__.py
  models.py
  ports.py

backend/application/rendering/
  __init__.py
  copy_resolver.py
  service.py

backend/infrastructure/assets/
  __init__.py
  filesystem.py

backend/infrastructure/rendering/
  __init__.py
  chromium.py

backend/infrastructure/mongo/rendering.py
backend/routes/rendering.py
backend/scripts/s5_generate_goldens.py

renderer/
  Dockerfile
  src/server.mjs

frontend/lib/rendering.ts
frontend/app/review/[revisionId]/
  page.tsx
  render-preview.tsx
  review.module.css
frontend/e2e/s5-review-preview.spec.ts

.github/workflows/s5-cert.yml
```

The renderer sidecar deliberately reuses the repository-locked Playwright `1.62.1` dependency graph from `frontend/package-lock.json`; S5 does not introduce a second drifting browser package lock.

## Feature flags

S5 reuses the frozen registry flag:

```text
MK1_RENDER_WORKER
```

The canonical API additionally requires `MK1_VISUALSPEC`. `MK1_ENABLED=false` forces both child authorities off through the existing master-gate semantics. S5 introduces no duplicate render flag.

## Domain contracts

### `RendererRequestV1`

Binds:

- deterministic `render_id` / `render_input_digest`;
- revision + VisualSpec identities and digests;
- ContentSpec + DesignProfile digests;
- exact canvas/safe-zone/theme values;
- resolved page/block payload;
- no free-form CSS, HTML, URL or editorial text authority.

Critical text is resolved from the exact `ContentSpecV1` through the S4 copy-reference map before renderer execution.

### `AssetV1`

Immutable product-owned asset metadata:

```text
asset_id
tenant_id
revision_id
render_id
visual_spec_id
page_id / page_index
content_type
width / height
byte_size
storage_key
sha256
render_input_digest
created_at
```

### `RenderResultV1`

Immutable complete render-set evidence:

```text
render_id
tenant_id
revision_id
visual_spec_id + digest
content_spec_digest
design_profile_digest
render_input_digest
renderer_name / renderer_version
assets[]
started_at / completed_at
```

The result is not accepted if the asset set disagrees with the exact VisualSpec page count or lineage.

## AssetStore implementation

`FilesystemAssetStore` implements the frozen local-first port under `PRODAGENTIC_ASSET_ROOT`.

Write sequence:

```text
caller bytes
→ generated traversal-free key
→ temp file
→ fsync
→ atomic replace
→ owned read-back
→ SHA-256
→ StoredBytes
```

Guards:

- no caller-selected arbitrary filesystem path;
- absolute path / `..` / backslash traversal rejected;
- symlink escape rejected;
- root escape rejected;
- deterministic duplicate is idempotent only when bytes match;
- restart/reopen uses the same configured durable root;
- asset hashes are verified again before preview/read use.

## Renderer implementation

`ChromiumRendererAdapter` is an HTTP adapter to an isolated renderer container.

Runtime properties:

- Playwright/Chromium `1.62.1`;
- bounded transport retry (maximum two adapter attempts);
- request/response renderer identity and digest verification;
- PNG only in the certified S5 V1 path;
- max page byte-size enforcement;
- sidecar port is container-internal in Compose (`expose`, not host `ports`);
- renderer request schema uses exact allowed fields;
- renderer token/color mapping is allowlisted;
- Chromium network requests are aborted;
- browser screenshots use exact VisualSpec canvas dimensions.

Generated-background/photo provider strategies remain fail-closed outside this certification unless separately implemented later.

## State and recovery semantics

Entry:

```text
GenerationRun.VISUAL_PLANNING
ContentRevision.DRAFT
visual_spec_ref/digest present
asset_refs == ()
qa_report_id == null
```

Successful S5 completion:

```text
GenerationRun.VISUAL_PLANNING
→ RENDERING
→ QA

ContentRevision.DRAFT
→ QA_PENDING

asset_refs = complete immutable AssetV1 ID tuple
qa_report_id = null
```

No `REVIEWABLE` or Approval transition is present in S5.

### Retryable failure

Renderer/AssetStore failures explicitly classified `retryable=True` remain:

```text
GenerationRun.RENDERING
failure = durable GenerationFailureV1
completed_at = null
```

The deterministic operation may be retried. A later successful completion clears the transient failure when the run enters `QA`.

### Non-retryable integrity failure

A deterministic integrity violation transitions the run to `FAILED` with terminal evidence. ContentSpec, VisualSpec and revision copy authority remain unchanged and no partial asset set is attached.

### Restart / partial-completion recovery

- an existing deterministic `RenderResultV1` is reverified instead of blindly re-rendered;
- persisted `AssetV1` metadata must still agree with owned bytes;
- revision asset binding is optimistic/CAS based;
- a QA-pending revision without its deterministic RenderResult fails closed;
- a run reaching QA without its deterministic RenderResult fails closed;
- mixed/partial asset generations cannot be attached as a successful revision set.

## Persistence / indexes

Mongo S5 collections:

```text
assets
render_results
```

Indexes:

```text
assets unique (tenant_id, asset_id)
assets (tenant_id, revision_id, page_index)
render_results unique (tenant_id, render_id)
render_results (tenant_id, revision_id, completed_at desc)
```

Stored Asset/RenderResult metadata includes canonical metadata digests checked on read. Tenant-scoped repositories remain structural.

## API surface

```text
POST /api/content-revisions/{revision_id}/render
GET  /api/render-results/{render_id}
GET  /api/render-assets/{asset_id}/content
GET  /api/content-revisions/{revision_id}/render-preview
```

Owned asset responses reverify the AssetStore SHA-256 before returning bytes and expose immutable ETag/cache metadata. Preview requires `QA_PENDING` plus a complete verified asset set.

## Review preview

Implemented route:

```text
/review/[revisionId]
```

The preview:

- renders owned assets;
- supports multi-page navigation;
- shows dimensions and SHA evidence;
- is responsive for desktop/mobile;
- exposes explicit `Rendered · QA pending` state;
- does not expose Approve.

S6/S7 remain responsible for QA/reviewability/approval.

## Test implementation

### Contracts / authority / AssetStore

`backend/tests/test_s5_rendering.py` covers:

- deterministic resolved renderer requests for single image/carousel/infographic;
- strict contract boundary;
- unsupported generated strategy rejection;
- known SHA-256 vector (`abc`);
- AssetStore restart/read-back;
- traversal/symlink rejection;
- complete asset binding;
- dimension mismatch failure without revision attachment;
- renderer failure preserving ContentSpec/VisualSpec authority;
- deterministic result reuse after restart/retry.

### Real Mongo

`backend/tests/test_mk1_s5_mongo.py` covers:

- run claim and S5 contract lineage;
- immutable AssetV1/RenderResultV1 persistence;
- restart/reopen;
- tenant isolation;
- CAS stale asset-binding rejection;
- persisted metadata tamper rejection.

`backend/tests/test_s5_retryable_recovery.py` separately proves:

- transient failure remains `RENDERING` and recoverable;
- successful retry clears failure and advances to `QA`;
- non-retryable integrity failure becomes terminal `FAILED`.

### API / flags

`backend/tests/test_s5_api_surface.py` proves the canonical OpenAPI routes and fail-closed render-worker feature semantics.

## Real Chromium golden evidence

`backend/scripts/s5_generate_goldens.py` produces real Chromium PNGs through the production adapter and real FilesystemAssetStore for:

```text
Content Seller      single_image   1 page
Logan / automotive carousel       2 pages
Tech / LinkedIn    infographic    1 page
```

For each page it validates the actual PNG IHDR dimensions (`1080 × 1350`), stores product-owned bytes, verifies read-back SHA-256 and emits a manifest containing exact Profile/ContentSpec/VisualSpec/DesignProfile/render identities and per-page hashes.

`S5-CERT` invokes the generator twice against the same AssetStore root so divergent supposedly deterministic bytes cannot silently pass as idempotent output.

## Desktop/mobile golden preview evidence

`frontend/e2e/s5-review-preview.spec.ts` consumes the exact real Logan PNGs generated in the same S5-CERT job, serves those owned bytes to the Review UI and certifies:

- desktop 1440×1100;
- mobile 390×844;
- actual image load (`naturalWidth` / `naturalHeight`);
- complete page navigation;
- explicit QA-pending state;
- no Approve action;
- screenshots retained in the S5 evidence artifact.

## Dedicated `S5-CERT`

Workflow:

```text
.github/workflows/s5-cert.yml
job: S5-CERT renderer-assetstore
```

The gate records exact run identity before tests and produces `s5-renderer-assetstore-evidence` even on failure. It runs:

1. compile S5 modules;
2. API/feature-flag gate;
3. S5 contracts/AssetStore/lifecycle tests;
4. real Mongo lineage/restart/CAS tests;
5. retryable recovery tests;
6. AST guard against S6/S7+ authority;
7. real isolated renderer Docker build/health;
8. real Chromium golden generation twice;
9. manifest dimension/page/hash checks;
10. Next.js production build/start;
11. desktop/mobile Playwright Review preview using exact golden bytes;
12. evidence inventory/log capture.

## Certification consensus required

No freeze occurs until **the same exact S5 candidate SHA** passes:

```text
1. backend-test
2. frontend-test
3. UI-01-CERT browser
4. DOCKER-COMPOSE-LOCAL smoke
5. S3-CERT structured-agent-cell
6. S4-CERT visualspec-v1
7. S5-CERT renderer-assetstore
```

Required closure sequence:

```text
reviewed implementation head
→ exact candidate 7/7
→ freeze candidate + certification receipt only
→ receipt head 7/7
→ exact-head merge
→ product merge main 7/7
→ optional docs-only descendant, separately revalidated
```

## Error / near-miss history

Canonical append-only ledger:

```text
mk1/build/slices/S5/ERROR_LEDGER.md
```

It includes architectural near-misses as well as actual implementation/process errors, including the unreferenced empty commit, delayed branch-ref advancement, incorrect terminalization of retryable failures and the initial recovery-test cleanup omission. These are intentionally preserved rather than erased before certification.

## Observability

S5 durable evidence includes:

- run/revision/VisualSpec/render identities;
- renderer adapter/version;
- exact input and asset digests;
- page count/dimensions;
- deterministic failure stage/code/retryability;
- persisted AssetV1/RenderResultV1 metadata;
- workflow run identity and golden evidence artifact.

No secrets/provider credentials are stored in these contracts.

## Rollback

- set `MK1_RENDER_WORKER=false` to disable S5 authority;
- S4 VisualSpec remains the certified upstream boundary;
- retained asset bytes are not destructively deleted during rollback;
- no destructive migration is authorized in S5;
- renderer sidecar may be removed from active runtime without changing S4 data.

## Known non-claims

S5 does **not** certify:

- semantic/claim QA;
- clipping/overlap/semantic visual QA or automatic visual recovery;
- `REVIEWABLE` state;
- human Approval / ApprovalBundleV2;
- export;
- Redis/outbox;
- scheduling/publication;
- analytics/learning;
- generated-image provider strategies outside the deterministic composed-static certified path.

Those remain S6+ authority.

## Certification evidence

Pending exact-SHA PR execution. No S5 product certificate has been declared yet.
