# PR-RUN-01 — Persistent ContentRun Foundation

## Status

IN REVIEW — implementation is on `feat/content-run-persistence`; merge is gated by CI.

## Problem

The generation pipeline already emitted a stable `run_id`, but persistence happened only after the full pipeline finished by inserting a legacy `posts` document. A process interruption could therefore leave no authoritative record of the run, and the saved post did not preserve stage lifecycle, selected model/provider, or retry failure state.

## Decision

Introduce `ContentRun` as the authoritative generation record. Keep the existing `posts` collection as a compatibility projection until the library/review workflow is migrated.

## Lifecycle

`GENERATING → TEXT_READY → READY_FOR_REVIEW`

Future states are reserved in the contract for the next release slices:

`APPROVED → SCHEDULED → PUBLISHING → PUBLISHED`

Terminal/supporting states:

`FAILED`, `CANCELLED`, `ARCHIVED`.

## Stage semantics

Each run records the four current production stages:

- research
- write
- edit
- visual

Each stage persists:

- status
- output
- selected model
- provider
- attempt failure count
- last error
- start/completion timestamps

Research/write/edit failures are terminal for the run. Visual failure is explicitly non-terminal: valid text can still reach `READY_FOR_REVIEW` without a generated visual.

## API

- `GET /api/content-runs`
- `GET /api/content-runs/{run_id}`

The list endpoint supports `limit` and optional lifecycle `status` filtering.

## Compatibility

- Generation still works when MongoDB is unavailable.
- Persistence failures are logged but do not become hidden generation dependencies.
- Existing `posts` documents continue to be written and now include `run_id` for traceability.

## Acceptance criteria

- A ContentRun is created before the first content stage starts.
- Stage start/completion/failure state is persisted during execution.
- `pipeline.text_completed` corresponds to persisted `TEXT_READY`.
- A successful generation ends at `READY_FOR_REVIEW`, never `APPROVED` or `PUBLISHED`.
- Visual failure does not fail the full run.
- Legacy post projection is linked to its authoritative `run_id`.
- Backend smoke import, compile check, and full tests pass in CI.
- Frontend lint, tests, and build remain green.

## Next slice after merge

`PR-RUN-02 — Content Library + Resume/Edit Surface`

The frontend will consume ContentRun history so a user can reopen a prior generation and continue from the saved artifacts rather than restarting the pipeline.
