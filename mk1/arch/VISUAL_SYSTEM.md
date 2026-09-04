# MK1 Visual Production Architecture

Status: **FROZEN FOR STATIC V1**

## Principle

Visual production separates **visual intent** from **render execution**.

```text
ContentSpecV1
   -> VisualAgent
   -> VisualSpecV1
   -> RendererPort
   -> owned Asset(s)
   -> Visual QA
```

## Why VisualSpec exists

A raw image prompt cannot reliably represent:

- carousel page semantics;
- deterministic editorial text;
- layout hierarchy;
- diagrams;
- typography;
- safe zones;
- asset provenance;
- multiple render strategies;
- re-rendering without rewriting copy.

VisualSpec is the stable intermediate representation.

# VisualSpecV1 envelope

```yaml
visual_spec_id: str
spec_version: 1
content_spec_id: str
revision_id: str
format: single_image|carousel|infographic
canvas:
  width: int
  height: int
  unit: px
  safe_zone: {top:int,right:int,bottom:int,left:int}
render_strategy: COMPOSED_STATIC|GENERATED_BACKGROUND|GENERATED_VISUAL_PLUS_COMPOSITE|DIAGRAM|CAROUSEL|INFOGRAPHIC|PHOTO_OVERLAY
visual_pattern: str
style:
  design_profile_ref: str
  density: sparse|balanced|dense
  image_treatment: str|null
  icon_language: str|null
pages: [VisualPageV1]
asset_requirements: [AssetRequirementV1]
alt_text_plan: str|null
```

# VisualPageV1

```yaml
page_id: str
page_index: int
role: hook|explain|evidence|example|takeaway|cta
layout_family: str
blocks: [VisualBlockV1]
```

Block union includes:

- `TextBlock`;
- `ShapeBlock`;
- `IconBlock`;
- `ImageBlock`;
- `DiagramBlock`;
- `DividerBlock`;
- `MetricBlock`.

## Critical copy references

`TextBlock` should normally use:

```yaml
copy_ref: "content_spec.format_spec.slides[slide-2].headline"
```

rather than free-generating critical text inside VisualAgent.

Decorative microcopy may use `literal` only when explicitly marked `editorial_critical=false`.

Renderer resolves copy references from the frozen ContentSpec and records the resolved render input digest.

# Render strategies V1

### COMPOSED_STATIC

Pure deterministic text/shapes/icons/layout.

### GENERATED_BACKGROUND

Model-generated background or illustration + deterministic overlay copy.

### GENERATED_VISUAL_PLUS_COMPOSITE

Generated central asset/scene + deterministic product composition.

### DIAGRAM

Structured nodes/edges/labels rendered deterministically.

### CAROUSEL

Multi-page composition from page list.

### INFOGRAPHIC

Structured information hierarchy in one or more canvases.

### PHOTO_OVERLAY

Owned/provided/generated photo + deterministic overlay.

GIF and SHORT_VIDEO are reserved for later spec versions; they are not required for V1 certification.

# RendererPort

```text
render(VisualSpecV1, ContentSpecV1, DesignProfile, resolved_assets) -> RenderResult
```

V1 adapter decision:

- generate HTML/SVG/CSS from typed layout data;
- render using headless Chromium/Playwright behind `ChromiumRendererAdapter`;
- write exact bytes through AssetStore;
- compute SHA-256 after owned bytes are written/read back;
- return owned Asset records.

The port permits later replacement without changing VisualSpec/domain contracts.

# DesignProfile

Profile-specific visual policy:

```text
typography roles
palette mapping
density
spacing/radius preferences
icon language
image treatment
layout family preferences
brand marks/safe zones
```

DesignProfile is inferred/preset-aware but versioned inside ProfileVersion or referenced by immutable version.

# Generated image boundary

Generated images are assets/components. They do not own critical text.

Provider adapter requirements:

- timeouts;
- bounded retry;
- content-type validation;
- byte-size limits;
- ownership/storage copy before approval;
- provider metadata recorded safely;
- remote ephemeral URL is not approval authority.

# Render validation

Deterministic checks include:

- dimensions/aspect ratio;
- expected page count;
- missing blocks/copy refs;
- font/layout overflow signals;
- asset availability;
- final file existence;
- digest integrity.

Visual model checks include:

- clipping/overlap;
- hierarchy/legibility;
- obvious artifacts;
- wrong/missing visible copy;
- content/visual mismatch;
- unsafe/inappropriate image semantics according to policy.

# Asset variants

A Revision may own multiple render variants, but Approval must identify the exact selected assets. Unselected variants remain provenance/history and cannot be published under that Approval.
