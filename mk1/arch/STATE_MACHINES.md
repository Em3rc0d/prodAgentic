# MK1 State Machines

Status: **FROZEN**

State transitions are application/domain decisions. Workers and agents request transitions; they do not invent states.

# Batch

```text
DRAFT
  -> PLANNING
  -> PLANNED
  -> PRODUCING
  -> REVIEWABLE
  -> CLOSED

Supporting:
CANCELLED
FAILED
```

A Batch may be `REVIEWABLE` while some items need attention. Item summary counts express mixed progress. `CLOSED` means the requested work cycle is no longer active; it does not imply every ContentItem was published.

# ContentItem editorial lifecycle

```text
CANDIDATE
  -> PLANNED
  -> PRODUCING
  -> READY_FOR_REVIEW
  -> APPROVED
```

Side states:

```text
REVISION_REQUIRED
REJECTED
FAILED
CANCELLED
ARCHIVED
```

Important semantics:

- `CANDIDATE` is not yet committed to production or editorial memory as a future audience promise.
- `READY_FOR_REVIEW` means the current revision passed required QA gates.
- `APPROVED` means at least the current accepted revision has an immutable Approval.
- creating a replacement revision after approval moves active editorial work through `REVISION_REQUIRED`/review flow while the prior Approval remains immutable historical authority.
- **Scheduled, Publishing and Published are not ContentItem editorial states.** They are target-specific Schedule/Publication states. One Approval may have several distribution targets with different outcomes.

For UI convenience, a derived distribution summary may say “2 scheduled · 1 published · 1 needs reconciliation”; it is not authoritative state.

# GenerationRun

```text
CREATED
 -> RESEARCHING
 -> WRITING
 -> EDITING
 -> VISUAL_PLANNING
 -> RENDERING
 -> QA
 -> COMPLETED
```

Terminal/supporting:

```text
FAILED
CANCELLED
```

Some format paths may skip rendering (e.g. text-only) but must still record the skipped stage explicitly rather than fabricate success.

# ContentRevision

```text
DRAFT
 -> QA_PENDING
 -> REVIEWABLE
 -> SUPERSEDED
```

A revision's content/asset identity becomes immutable at `REVIEWABLE`. User edit/regeneration creates a new revision instead of rewriting a reviewable revision. Approval is a separate aggregate, not a revision state.

# QAReport

Verdict values:

```text
PASS
PASS_WITH_WARNINGS
FAIL
```

Only policies marked approval-blocking prevent review/approval. Warnings remain visible with rationale.

# Schedule

```text
SCHEDULED
 -> DISPATCHED
 -> COMPLETED
```

Side states:

```text
CANCELLED
FAILED
```

`DISPATCHED` means an execution job has been durably requested/published through the outbox/transport path; it does not mean a public post exists.

When its Publication becomes `PUBLISHED`, the Schedule may become `COMPLETED`. When Publication proves a known-safe failure, it may become `FAILED`. While Publication is `RECONCILIATION_REQUIRED`, Schedule remains dispatched/pending outcome rather than pretending failure or success.

# Publication

```text
PENDING
 -> PUBLISHING
 -> PUBLISHED
```

Known pre-success failure:

```text
PUBLISHING -> FAILED_SAFE
```

Uncertain external side effect:

```text
PUBLISHING -> RECONCILIATION_REQUIRED
```

After reconciliation:

```text
RECONCILIATION_REQUIRED -> PUBLISHED
RECONCILIATION_REQUIRED -> FAILED_SAFE
```

Only a reconciliation procedure may resolve uncertainty. Automatic generic retry may not.

# JobOutbox

```text
PENDING
 -> ENQUEUED
 -> ACKNOWLEDGED
```

Support:

```text
DEAD
```

Outbox state is execution evidence only. Domain state remains in the corresponding Schedule/Publication/Asset/Analytics entities.
