# ADR-0004 — Mongo authority + Redis Streams + Mongo outbox

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

Schedules, approvals and publication receipts are durable business truth. Redis is useful for worker coordination but must not become a second competing source of truth or a loss point between Mongo updates and queue writes.

## Decision

MongoDB remains system of record. Redis Streams/consumer groups carry V1 render, publish and analytics jobs. A deterministic Mongo `job_outbox` records durable dispatch intent; dispatcher redrives it to Redis. Workers perform authoritative Mongo claims before side effects.

## Consequences

- Redis can be rebuilt/lost without erasing schedules;
- duplicate queue delivery is expected and handled;
- outbox/dispatcher logic becomes a required subsystem;
- operations must monitor both domain backlog and stream backlog.

## Alternatives

Celery/RQ as primary task authority — rejected for now because domain idempotency/outbox is required regardless and Redis Streams provides sufficient V1 primitives. Mongo-only polling — rejected as worker transport target due to limited coordination/observability and current product direction.

## Revisit

If throughput/operational needs justify another broker/task framework, keep `JobTransport` and outbox contracts stable.
