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

# ContentItem

```text
CANDIDATE
  -> PLANNED
  -> PRODUCING
  -> READY_FOR_REVIEW
  -> APPROVED
  -> SCHEDULED
  -> PUBLISHING
  -> PUBLISHED
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
- `READY_FOR_REVIEW` means current revision passed required QA gates.
- `APPROVED` means an immutable Approval exists for the latest accepted revision.
- `PUBLISHING` is an external side-effect uncertainty boundary and cannot be blindly replayed.
- creating a new revision after approval moves active work to `REVISION_REQUIRED`/review flow while the prior Approval remains historical evidence.

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

Approval is a separate aggregate, not a revision state. A reviewable revision can become the source of an Approval. When a newer revision is created, older non-approved revisions may be marked superseded.

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

`DISPATCHED` means an execution job has been created/published through the outbox/transport path; it does not mean a public post exists.

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
