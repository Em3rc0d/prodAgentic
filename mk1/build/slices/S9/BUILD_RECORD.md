# S9 BUILD RECORD — Redis Streams + Mongo Outbox

Status: CANDIDATE — certification required before closeout.

## Authority

Base:
`main@56919f45cb685ec907697877059ce4b2b44b8fa7`

Frozen contracts:
- `mk1/plan/VERTICAL_SLICES.md` — S9 flow and exits.
- `mk1/arch/adr/ADR-0004-MONGO-REDIS-OUTBOX.md`.
- `mk1/arch/INVARIANTS.md`.

## Slice boundary

S9 introduces durable transport mechanics only:

`Mongo intent -> Outbox -> Redis Streams -> worker -> Mongo claim -> ACK`

MongoDB remains the system of record. Redis may duplicate, lose, or redeliver
messages without becoming business authority.

S9 does **not**:
- schedule LinkedIn publication;
- call a LinkedIn provider;
- mark publication business success;
- acquire S10 publisher authority.

## Implemented contracts

- deterministic tenant-bound job identity and payload SHA-256;
- durable `job_outbox` records in Mongo;
- tenant-scoped outbox reads and CAS-style execution leases;
- rediscovery/redrive of incomplete Mongo jobs;
- Redis Streams consumer groups;
- command-scoped Redis connections so broker restart does not pin stale sockets;
- at-least-once duplicate delivery absorbed by Mongo execution claims;
- `XAUTOCLAIM` pending-consumer recovery;
- explicit DLQ transport that leaves business state `DEAD_LETTERED`, never success;
- separate domain backlog and stream/PENDING lag metrics;
- Redis carries job identity + digest only; business payload stays in Mongo;
- local Compose overlay at `docker-compose.s9.yml`.

## S9-CERT required evidence

The dedicated workflow must prove on one exact SHA:

1. deterministic job identity and tenant isolation;
2. duplicate delivery causes at most one claimed side-effect execution;
3. Redis stream loss is redriven from durable Mongo intent;
4. abandoned PEL messages are recoverable with `XAUTOCLAIM`;
5. real Redis restart reconnects successfully;
6. DLQ cannot be interpreted as business success;
7. domain and Redis lag metrics exist;
8. S9 source does not import/call S10 publishing/scheduling authority;
9. base CI, Docker, and S3-S8 remain green.

Only after all gates are green may the PR merge. Post-merge consensus must be
repeated on the resulting `main` SHA before S9 becomes `CERTIFIED/CLOSED`.
