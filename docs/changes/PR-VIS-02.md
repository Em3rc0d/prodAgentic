# PR-VIS-02 — ContentRun Visual Artifact Ownership

## Objective

Make rendered media part of the authoritative `ContentRun` instead of leaving the generated image as transient frontend state or an unlinked file on disk.

This is a prerequisite for approval: prodAgentic must know exactly which text and which visual artifact are being reviewed before a run can cross into `APPROVED`.

## Scope

### Canonical visual snapshot

`ContentRun.visual_render` now captures:

- `render_id`
- `status`
- `provider`
- `asset_url`
- dimensions
- provider `prompt_used`
- human/requested prompt
- aspect ratio
- visual style
- idempotency key
- error message
- rendered timestamp

### Render attachment

`POST /api/visual-renders` keeps image generation independent from MongoDB availability, but after each render attempt it tries to attach the result to the matching reviewable `ContentRun`.

Attachment is allowed only while the run is:

```text
TEXT_READY
READY_FOR_REVIEW
```

Attachment is rejected once the run has crossed the review boundary, including:

```text
APPROVED
SCHEDULED
PUBLISHING
PUBLISHED
```

A fallback or unknown `run_id` can still render an image but cannot manufacture a persisted ContentRun.

### Stale-artifact invalidation

When a user changes `visual_prompt` through the review edit API:

```text
visual_prompt changes
        -> visual_render = null
        -> a replacement image must be rendered
```

Changing only `final_content` does not invalidate a still-current visual artifact.

Submitting the same visual prompt again does not invalidate it.

### Idempotency hardening

A render idempotency key is now bound to exactly one render intent:

```text
(prompt, aspect_ratio, style)
```

- same key + same intent -> returns the original artifact
- same key + different intent -> explicit FAILED response

This prevents an old image from being returned and attached after a prompt or rendering-parameter change.

### Cross-host asset resolution

Backend render responses intentionally keep storage paths backend-relative (`/assets/renders/...`). The frontend resolves those paths against `NEXT_PUBLIC_API_URL`, so separate frontend/backend deployments do not accidentally request render assets from the Next.js host.

### Library continuation

`/library/{run_id}` now:

- displays the current owned render artifact
- displays render status/provenance
- permits prompt, aspect-ratio and style review before approval
- can render or replace the visual directly from a reopened run
- saves human edits before rendering so the new image is attached to the current authoritative prompt

## Invariants

1. An approved-or-later run cannot have its visual artifact overwritten.
2. A changed visual prompt can never retain a stale render as current evidence.
3. A render persistence failure cannot fabricate a rendering failure.
4. An unknown run ID cannot create a ContentRun implicitly.
5. A reused idempotency key cannot resolve to a different render intent.
6. Approval must consume the owned `ContentRun.visual_render`, never transient frontend state.

## Acceptance criteria

- successful render is attached to a reviewable ContentRun
- failed render attempts can also be represented as the current render attempt
- approved ContentRuns reject artifact replacement
- changing visual prompt clears prior visual ownership
- final-copy-only edits preserve current render ownership
- same idempotency key + same intent is deterministic
- same idempotency key + different intent fails explicitly
- backend-relative asset paths resolve against the configured backend origin
- reopened library runs can render a replacement visual
- backend compile/tests and frontend lint/tests/build are green

## Explicitly out of scope

- approval transition itself
- immutable approval snapshot/hash
- LinkedIn media upload
- scheduling
- long-term object storage/CDN migration

## Next slice

`PR-APPROVAL-01 — Review + Approval contract`

That slice may now safely freeze a complete publishable asset composed of:

```text
final_content
+
visual_render (when visual media is required)
+
review metadata
```
