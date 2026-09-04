# MK1 Execution Architecture

Status: **FROZEN**

## Goal

Separate durable business authority from transient work transport while supporting restart recovery, multi-worker safety and observable failure handling.

# Redis decision

V1 uses **Redis Streams with consumer groups** through `redis-py` behind a `JobTransport` port.

Streams:

```text
pa:render:v1
pa:publish:v1
pa:analytics:v1
```

Consumer groups are worker-role specific. Dead-letter streams:

```text
pa:render:v1:dead
pa:publish:v1:dead
pa:analytics:v1:dead
```

Redis is not the source of truth.

# Why Streams

- explicit acknowledgement;
- pending-entry visibility;
- consumer groups;
- recoverable at-least-once delivery;
- fewer framework semantics than adopting a large task framework before the domain is stable;
- easy to wrap behind a port if later replacement is justified.

# Mongo outbox

The system must not rely on a single fragile sequence “update Mongo -> XADD Redis”.

A deterministic Mongo `job_outbox` record is the durable dispatch intent.

## Operation key

Example:

```text
sha256(job_type + entity_id + approval_bundle_digest + operation_version)
```

The exact canonical composition is versioned/tested.

## Dispatch sequence

```text
1. application/domain determines operation is due/required
2. upsert deterministic outbox record PENDING
3. dispatcher reads PENDING/unconfirmed outbox records
4. XADD JobEnvelopeV1 to Redis Stream
5. mark outbox ENQUEUED with stream id
6. worker consumes
7. worker performs authoritative domain claim in Mongo
8. worker executes adapter
9. worker persists domain result/receipt
10. ACK Redis
11. mark outbox ACKNOWLEDGED where useful
```

If the dispatcher crashes after XADD before marking ENQUEUED, redelivery may duplicate the job. The worker/domain idempotency contract makes that safe.

# Scheduler

The scheduler queries Mongo for due `SCHEDULED` records and creates deterministic publish outbox jobs. It does not publish externally and does not mutate content bytes.

Multiple scheduler instances are permitted because outbox operation keys are unique/idempotent.

# Worker claim rule

Transport possession does not equal publication authority.

A publish worker must atomically claim the Publication/ContentItem transition using expected current state + approval/bundle identity before any external call.

A duplicate transport message that fails the authoritative claim becomes a no-op/inspection case.

# Pending entry recovery

Workers inspect consumer-group pending entries. Entries whose consumers disappeared may be claimed after a visibility timeout only for operations whose domain state proves replay is safe.

For publication:

- if domain is still pre-external `PENDING` and no claim occurred, safe to claim;
- if domain is `PUBLISHING`, do not replay blindly — reconcile.

# Dead-letter policy

Move a transport message to DLQ only after bounded technical delivery/execution attempts and safe domain inspection.

DLQ includes safe identifiers, failure classification and original job envelope. It does not mark business entities completed.

# Feature flags

Initial flags:

```text
MK1_REDIS_TRANSPORT
MK1_RENDER_WORKER
MK1_PUBLISH_WORKER
MK1_ANALYTICS_WORKER
```

Flags permit parallel certification against MK0 paths without silently changing authority.

# Backpressure

Metrics:

- stream length;
- pending count;
- oldest job age;
- consumer lag;
- DLQ count;
- domain due-schedule age.

The API may accept work while workers are degraded only when it can honestly persist the request and surface delayed state.
