# ADR-0001 — Modular monolith + separately runnable workers

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK1 introduces more domain boundaries, agents, queues and adapters, but current scale does not justify network-distributed business services. Premature microservices would multiply deployment, consistency and observability complexity.

## Decision

Keep FastAPI as a modular monolith with explicit domain/application/infrastructure modules. Run render, publish and analytics workers as separate processes using the same codebase/packages.

## Consequences

- boundaries are testable without distributed calls;
- one repository and release train remains possible;
- workers can scale independently enough for V1;
- module rules must be enforced because deployment boundaries will not enforce them for us.

## Alternatives

Microservices now — rejected as unproven operational cost. One single process — rejected because long-running/external work needs isolated worker lifecycle.

## Revisit

When measured scale, ownership, failure isolation or release cadence demonstrates a module needs independent deployment and the data/contract boundary is already stable.
