# ADR-0010 — Capability-aware adapters + manual fallback

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

Social platforms differ in auth, formats, limits, scheduling and analytics. Hard-coding one assumed capability matrix would make UI/Planner lie or break as APIs change.

## Decision

Each connected adapter exposes `PlatformCapabilityV1`. LinkedIn is the first automatic V1 adapter. Unsupported channels use `ManualExport` with exact approved content/assets/manifest instead of simulated automation.

## Consequences

- planner/UI can adapt honestly;
- integrations do not block the core content job;
- capability snapshots need freshness/version evidence.

## Revisit

Promote additional automatic adapters only after capability quarry + contract tests + live certification.
