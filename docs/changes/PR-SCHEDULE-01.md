# PR-SCHEDULE-01 — Durable Scheduling

## Product gate

Scheduling is a durable trigger over the existing immutable approval and LinkedIn publication contract. It must never create a second publishing implementation.

## Lifecycle

```text
APPROVED
   ↓ explicit schedule
SCHEDULED
   ↓ due-time atomic claim
PUBLISHING
   ↓ LinkedIn success + evidence
PUBLISHED
```

Cancellation is allowed only before the atomic due-time claim:

```text
SCHEDULED -> APPROVED
```

## Time contract

The API accepts only timezone-aware ISO datetimes. Naive timestamps are rejected.

The frontend `datetime-local` value represents the browser's local time. It is converted with `Date.toISOString()` before submission, preserving one exact UTC instant for storage and worker comparison.

Past or current instants are rejected.

## Schedule snapshot

Each scheduled ContentRun stores:

- schedule ID
- status
- exact `scheduled_for` UTC instant
- approval ID
- approval bundle SHA-256
- creation / claim / completion / cancellation timestamps
- safe failure detail

Scheduling never copies or rewrites content.

## Worker

The FastAPI lifespan runs a scheduler loop when `SCHEDULER_ENABLED=true`.

Configuration:

- `SCHEDULER_ENABLED` default `true`
- `SCHEDULER_POLL_SECONDS` default `30`, minimum effective value `5`

Every iteration queries due `SCHEDULED` runs and invokes the same `PublicationCoordinator` used by manual publishing.

## Multi-instance safety

Multiple application instances may discover the same due schedule. Publication ownership is determined only by Mongo's atomic status claim matching:

- run ID
- current `SCHEDULED` state
- approval ID
- approval bundle digest

Only the winner crosses to `PUBLISHING`; losers observe a conflict and do nothing.

## Crash safety

A crash after the external LinkedIn call but before local evidence finalization leaves the ContentRun in `PUBLISHING`. The worker does not reclaim or replay `PUBLISHING`, because doing so could duplicate a public post. This state requires reconciliation.

Known provider failure before confirmed post evidence returns the run to `APPROVED` with the schedule marked `FAILED`, allowing an explicit reschedule/retry.

## Frontend

`/scheduling` provides:

- approved and scheduled queue
- browser-local date/time selection
- explicit Schedule LinkedIn post action
- exact persisted schedule visibility
- cancellation before claim
- evidence link back to ContentRun

## Acceptance

1. Only APPROVED runs can be scheduled.
2. Scheduling requires configured LinkedIn publishing.
3. Timestamp must contain timezone information and be in the future.
4. Schedule stores approval identity and bundle digest.
5. Cancellation is atomic and fails if a worker already claimed the schedule.
6. Due worker calls the shared publication coordinator with `SCHEDULED` as its expected state.
7. Multi-instance discovery cannot create multiple claims.
8. PUBLISHING is never automatically replayed.
9. Scheduler task is cancelled cleanly at application shutdown.
10. Backend tests, frontend tests, lint, compile and Next build must be green before merge.
