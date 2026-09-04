# ADR-0002 — Split MK0 ContentRun responsibilities

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK0 `ContentRun` carries generation stages, mutable review copy, visual artifact, approval, schedule and publication snapshots. This was useful for proving the lifecycle but blocks clearer batch planning, revisions and independent execution evidence.

## Decision

MK1 uses first-class `Batch`, `ContentItem`, `GenerationRun`, `ContentRevision`, `Approval`, `Schedule` and `Publication` entities. `ContentItem` is conceptual editorial identity; runs/revisions are attempts/artifacts; approval and publication are separate authority/side-effect aggregates.

## Consequences

- regeneration/revision history becomes natural;
- approval can bind one exact revision cleanly;
- publication no longer mutates a generation aggregate;
- migration requires a compatibility/read strategy for MK0 data.

## Revisit

Only if actual implementation proves an entity has no independent lifecycle or invariants; merge boundaries only with evidence, never for convenience alone.
