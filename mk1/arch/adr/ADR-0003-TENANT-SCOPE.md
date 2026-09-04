# ADR-0003 — Tenant scope from day one

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK0 is explicitly single-admin. Adding tenant identity after production data accumulates is expensive and dangerous.

## Decision

Every new MK1 business entity includes `tenant_id`; server-side authenticated context supplies tenant authority. The first deployment may bootstrap exactly one Tenant and reuse existing session auth while domain storage is already tenant-safe.

## Consequences

- future multi-user/commercial accounts do not require re-keying the entire domain;
- all repository/query code must prove tenant scoping;
- existing MK0 records need migration mapping to bootstrap tenant.

## Revisit

The tenant root is not expected to be removed. Authorization models above it may change independently.
