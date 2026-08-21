# PR-RUN-02 — Content Library + Reopen/Edit

## Objective

Turn persisted `ContentRun` records into an operable product surface. A user must be able to leave prodAgentic, return later, find prior work, inspect the full generation lineage, and safely edit the human-owned review artifacts without rerunning the AI pipeline.

## Scope

### Backend
- `PATCH /api/content-runs/{run_id}`
- only `TEXT_READY` and `READY_FOR_REVIEW` runs are mutable
- editable fields are restricted to:
  - `final_content`
  - `visual_prompt`
- stage outputs, models/providers, attempt history, topic, idea, and lifecycle status are immutable through the edit contract
- legacy `posts` projection remains coherent when final copy changes
- blank final content is rejected

### Frontend
- `/library` lists persisted ContentRuns newest first
- status filters make the operational queue readable
- `/library/{run_id}` reopens a run
- full stage lineage remains visible and read-only
- final LinkedIn content and visual prompt are editable only before approval
- global product navigation exposes Create and Library without modifying the generation state machine

## Lifecycle invariant

```text
GENERATING
  -> TEXT_READY
  -> READY_FOR_REVIEW

Library edits are allowed only in:
  TEXT_READY
  READY_FOR_REVIEW

Library edits are rejected in:
  APPROVED
  SCHEDULED
  PUBLISHING
  PUBLISHED
  FAILED
  CANCELLED
  ARCHIVED
```

## Acceptance criteria

- a persisted run appears in `/library`
- selecting a run opens `/library/{run_id}`
- research/write/edit/visual provenance is visible after reload
- final content can be edited and saved in reviewable states
- visual prompt can be edited or cleared in reviewable states
- saved final content is mirrored to the legacy post projection while that compatibility layer exists
- an approved or later run returns HTTP 409 on edit
- whitespace-only final content is rejected
- existing generation pipeline behavior remains unchanged
- backend tests, frontend tests, lint, compile, and Next build are green

## Explicitly out of scope

- approval action
- content profiles
- LinkedIn authentication/publication
- scheduling
- analytics
- automatic reruns from a persisted run

## Next slice

`PR-APPROVAL-01 — Review + Approval contract`

Before that approval slice closes, the rendered visual artifact must also be attached authoritatively to the ContentRun so approval can freeze both text and visual evidence together.
