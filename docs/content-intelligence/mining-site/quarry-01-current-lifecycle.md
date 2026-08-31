# Quarry 01 — Current Trusted Lifecycle

## Question

What trusted lifecycle already exists, and therefore must not be reimplemented by Content Intelligence?

## OBSERVED

From the current release branch:

1. `ContentRunStatus` includes:
   - `GENERATING`
   - `TEXT_READY`
   - `READY_FOR_REVIEW`
   - `APPROVED`
   - `SCHEDULED`
   - `PUBLISHING`
   - `PUBLISHED`
   - terminal/administrative states.

2. `ContentRun` persists:
   - topic/style/idea,
   - content profile snapshot,
   - generation stage snapshots,
   - final content,
   - visual prompt/render snapshot,
   - approval snapshot,
   - schedule snapshot,
   - publication snapshot.

3. Human review edits are allowed only in reviewable states.

4. Approval:
   - requires `READY_FOR_REVIEW`,
   - hashes final content,
   - optionally includes a READY visual artifact,
   - freezes a bundle SHA-256,
   - uses optimistic concurrency based on the run update timestamp.

5. Publication:
   - is owned by `PublicationCoordinator`,
   - uses the immutable approval snapshot rather than mutable draft fields,
   - atomically claims `APPROVED` or `SCHEDULED` into `PUBLISHING`,
   - records attempt identity and external post/image evidence,
   - returns already-published same-bundle evidence instead of creating a new post.

6. Scheduling:
   - binds approval identity + bundle digest,
   - uses timezone-aware instants,
   - calls the same publication coordinator,
   - relies on Mongo atomic claim for multi-instance safety.

7. `PUBLISHING` is intentionally not auto-replayed because external success may have occurred before local evidence finalization.

8. Visual render artifacts include locally-owned asset URL and SHA-256 evidence; publication rechecks bytes before upload according to documented publisher contract.

## INFERRED

- `ContentRun` is already the correct aggregate to attach compact intelligence snapshots/references.
- Creating a parallel "content intelligence lifecycle" would introduce duplicated state and conflict risk.
- New features should enrich review and pre-publication decisions without changing the existing state machine unless a separately justified invariant requires it.

## PROPOSED

Add compact evidence dimensions:

- `workspace_id`
- `memory_check`
- `grounding`
- `visual_intent`

Do not add top-level statuses such as `MEMORY_CHECKED` or `GROUNDING_READY`.

## REJECTED

- A second publisher for intelligence-enabled posts.
- A separate scheduler.
- A second approval model.
- Reading mutable root draft fields after approval to decide what to publish.

## UNKNOWN

- Real LinkedIn external smoke publication remains a separate external gate; deterministic/injected publication tests do not prove a live account accepted/displayed the post.

## Pre-build verdict

PASS — trusted lifecycle foundation exists and should be preserved.