# MK1 User Journeys

Status: **FROZEN**

## Journey A — First useful batch

```text
Sign in
  -> Profiles / onboarding
  -> name + account type
  -> goals
  -> audience
  -> voice
  -> optional examples
  -> inferred Profile preview
  -> Looks good
  -> Create
  -> Generate tomorrow
  -> progress summary
  -> Review
  -> approve pieces
  -> Calendar / export
```

### Acceptance

- no requirement to configure agents/models/providers;
- examples can replace multiple manual settings;
- safe defaults exist if examples are skipped;
- first batch is generated against the new Profile snapshot.

## Journey B — Returning operator, routine day

```text
Home
  -> “Generate next batch”
  -> target window defaults to next sensible window
  -> system reviews recent memory
  -> system plans candidate pool and batch
  -> user gets notification when reviewable in the same request lifecycle/UI
  -> Review
  -> approve / make one local correction
  -> Schedule
```

The routine journey should feel like operating a product, not configuring a workflow.

## Journey C — Novelty collision

System finds a candidate too similar to recent content.

Default behavior:

```text
candidate blocked/reworked internally
```

If enough alternatives exist, the user never needs to intervene.

If the batch cannot meet requested size without a meaningful collision:

> “We found only 3 sufficiently fresh pieces for this window.”

Options:

- Keep 3
- Broaden strategy
- Review blocked candidate

Advanced details may show prior matching content and overlap categories.

## Journey D — QA recovery

Example: text clips in a carousel.

```text
Visual QA FAIL
  -> automatic layout correction
  -> rerender
  -> QA PASS
```

User sees only the recovered Ready state.

If recovery budget is exhausted:

> “1 visual needs review. The copy is safe and unchanged.”

Actions:

- Retry visual
- Use simpler layout
- Approve text only when platform/content format permits

## Journey E — Edit one piece

The user edits caption text.

System uses dependency-aware invalidation:

- copy-related QA reruns;
- VisualSpec/asset invalidates only if onscreen content or semantic coupling changed;
- previous runs remain in history;
- previous approval, if any, is not silently modified.

The UI explains only the relevant effect, e.g.:

> “Visual will be refreshed because this copy appears on slide 2.”

## Journey F — Approval

A piece is reviewable only after required QA gates.

User presses **Approve**.

The system freezes the exact approved content package. The UI then removes mutable editing actions from that approval revision and offers schedule/export.

If the user wants changes later, the system creates a new revision/run and requires a new approval rather than mutating history.

## Journey G — Scheduled publication

```text
Calendar
  -> choose approved item
  -> choose connected capable channel
  -> choose time
  -> schedule
```

The user sees:

- exact local time and timezone;
- channel/identity;
- status;
- final result/receipt.

A queue retry is not a user-visible event unless it affects the outcome.

## Journey H — Publication uncertainty

If provider success may have occurred but local evidence was not finalized:

> “Publication status needs reconciliation. We will not retry automatically because that could create a duplicate.”

The UI must not show Failed or retry blindly.

## Journey I — Unsupported platform

When automatic publishing is unavailable:

```text
Approved content
  -> Export package
  -> asset(s) + caption + platform notes + manifest
```

The user still completes the content job. Platform integration is not allowed to hold content hostage.

## Journey J — Learn from performance

Analytics summarizes observed patterns with confidence/context:

> “Technical diagrams have outperformed single-image explainers across the last 8 comparable Tech posts.”

It must not claim causation from weak samples or automatically force the next batch to repeat the same mechanic.
