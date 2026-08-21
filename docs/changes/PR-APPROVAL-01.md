# PR-APPROVAL-01 — Explicit Human Review + Immutable Approval Bundle

## Objective

Introduce the first hard human-control boundary in prodAgentic.

The multi-agent pipeline may generate, research, write, edit, and propose visuals, but it must never make content publishable merely because generation completed. Only an explicit human action may transition a `ContentRun` from review into an approved publishable asset.

## Lifecycle transition

```text
GENERATING
  -> TEXT_READY
  -> READY_FOR_REVIEW
  -> [explicit human approval]
  -> APPROVED
```

Only `READY_FOR_REVIEW` may cross this boundary.

`TEXT_READY`, `GENERATING`, `FAILED`, `CANCELLED`, and any already-approved-or-later state cannot invoke approval.

## Explicit bundle choice

Approval requires an explicit decision:

```text
include_visual = false
  -> approve exact final text only

include_visual = true
  -> approve exact final text + current owned visual artifact
```

There is no implicit visual omission and no automatic selection based solely on what the frontend happens to display.

## Visual approval requirements

When `include_visual=true`, the authoritative `ContentRun.visual_render` must:

- exist
- have `status=READY`
- have a persisted `asset_url`
- have an `asset_sha256` derived from the actual persisted bytes
- have `requested_prompt` equal to the current `ContentRun.visual_prompt`

If any requirement fails, approval returns HTTP 409 and the run stays `READY_FOR_REVIEW`.

## Immutable evidence

Each successful approval stores an `approval` snapshot containing:

- unique `approval_id`
- `approved_at`
- `source=explicit_user_action`
- explicit `include_visual` decision
- exact approved `final_content`
- `final_content_sha256`
- exact approved visual snapshot when included
- `visual_render_sha256` for the visual snapshot
- `bundle_sha256` binding the approved text/visual decision together

For READY image renders, `asset_sha256` is computed from the downloaded image bytes before those bytes are persisted to disk.

## Concurrency safety

Approval uses optimistic concurrency.

The backend reads the candidate review revision and then performs the transition only if all of these still match:

```text
run_id
status = READY_FOR_REVIEW
updated_at = reviewed revision
```

Every review edit and every attached render changes `updated_at`.

Therefore, if another edit or render lands between review and approval, the approval update misses and returns HTTP 409 rather than freezing a stale revision.

## Post-approval immutability

Existing contracts now compose into a real freeze boundary:

- review edit API rejects `APPROVED` and later states
- visual artifact attachment rejects `APPROVED` and later states
- approval itself only accepts `READY_FOR_REVIEW`

The root ContentRun remains available for lineage, but future publishing must consume `ContentRun.approval` as its source of publishable truth.

## Frontend behavior

`/library/{run_id}` exposes approval only when the run is `READY_FOR_REVIEW`.

The user gets two explicit actions:

- **Approve text only**
- **Approve text + visual**

Rules:

- approval controls are disabled while unsaved review edits exist
- text + visual approval is disabled unless the current visual has READY status and an asset digest
- after approval, editing and visual replacement controls become unavailable
- the approved bundle displays approval timestamp and shortened evidence digests

## Publisher contract carried forward

When LinkedIn publishing is implemented, the publisher MUST:

1. read from `ContentRun.approval`, not mutable root review fields
2. recompute the current media file SHA-256 before upload when a visual is included
3. compare it to `approval.visual_render.asset_sha256`
4. abort publication if the bytes no longer match
5. preserve the approval/bundle digest in publication evidence

This ensures a file changed after approval cannot silently be published under an older approval.

## Acceptance criteria

- READY_FOR_REVIEW text can be explicitly approved as text-only
- READY_FOR_REVIEW text + current READY visual can be explicitly approved together
- text approval stores exact text and deterministic SHA-256 evidence
- visual approval stores the owned render and its evidence digests
- missing visual digest blocks visual approval
- stale visual prompt blocks visual approval
- non-reviewable lifecycle states block approval
- concurrent review mutation blocks approval
- approved run becomes immutable through existing edit/render APIs
- rendered asset digest is proven to equal SHA-256 of persisted bytes
- frontend sends the explicit `include_visual` choice
- frontend displays approved bundle evidence
- backend smoke/compile/tests and frontend lint/tests/build are green

## Explicitly out of scope

- authentication / approver identity attribution
- approval reversal / reopening
- LinkedIn OAuth and publication
- scheduling
- team approvals or multi-person review
- cryptographic signing / external evidence ledger

## Next slice

`PR-PROFILE-01 — Content Profiles foundation`

Then:

```text
PR-PUBLISH-01 — LinkedIn publishing provider
PR-SCHEDULE-01 — durable scheduling
PR-PROD-01 — production/security hardening
PR-RELEASE-01 — end-to-end release certification
```
