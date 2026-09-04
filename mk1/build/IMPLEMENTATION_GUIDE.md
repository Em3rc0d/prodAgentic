# MK1 Implementation Guide

Status: **READY WHEN BUILD GATE PASSES**

## Backend target boundaries

Incrementally converge toward:

```text
backend/
  domain/
    tenants/
    profiles/
    batches/
    content/
    memory/
    approvals/
    publishing/
    analytics/
  application/
    profiles/
    planning/
    production/
    qa/
    review/
    scheduling/
    publishing/
    analytics/
  agents/
    planner/
    research/
    writer/
    editor/
    visual/
    routing/
  infrastructure/
    mongo/
    redis/
    assets/
    llm/
    images/
    renderer/
    platforms/
  workers/
    render/
    publish/
    analytics/
  api/
```

Do not reorganize the whole repository in one mechanical PR. Move/create boundaries as each slice needs them.

## Frontend target boundaries

```text
frontend/
  app/
    home/
    profiles/
    create/
    review/
    calendar/
    analytics/
  features/
    control-center/
    profiles/
    batch-create/
    review/
    calendar/
    analytics/
  components/
    product/
  lib/
    api/
    auth/
    telemetry/
```

Feature code owns user workflows; generic components do not contain domain-specific network behavior.

## Contract-first rule

Before a slice calls an agent/worker/adapter, define and test the Pydantic/TypeScript contract. Generate/maintain matching frontend types through a controlled OpenAPI/type step when practical; do not maintain two divergent handwritten truth sources indefinitely.

## Repository interfaces

Application services use repository ports. Infrastructure implementations enforce tenant scope and optimistic concurrency.

Avoid letting route handlers directly mutate Mongo collections for MK1 entities.

## Feature flags

New authority-changing paths begin behind flags. A flag does not excuse different domain semantics; it chooses which certified path is active.

## Error model

Use stable machine error codes plus safe user messages. Provider stack traces belong in diagnostics/logs, not public API error bodies.

## Migrations

Every schema migration includes:

- forward function/script;
- idempotency expectation;
- verification query;
- rollback/restore path where possible;
- count/checksum evidence;
- tenant mapping.

## Documentation coupling

A PR that changes an accepted contract must update the corresponding MK1 doc/ADR/design graph in the same PR, or explicitly state why the change is implementation-only.
