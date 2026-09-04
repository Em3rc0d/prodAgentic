# ADR-0005 — Batch-first planning with Editorial Memory and Novelty

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

Piece-first idea generation can repeat recent audience concepts or produce four internally similar posts even if each individual output is acceptable.

## Decision

Every routine multi-piece request creates a first-class Batch. Planner reads recent Editorial Memory, generates a larger candidate pool, applies hard policy/novelty gates and selects a role/angle/creative-diverse set before production.

Novelty is multi-layer: taxonomy, aliases, semantics, angle, creative pattern, visual pattern and intra-batch comparison.

## Consequences

- memory becomes a product subsystem, not prompt text;
- candidate rejection is normal/observable;
- exact similarity thresholds remain calibratable policy against golden datasets.

## Revisit

Selection algorithm may change after benchmark evidence, but batch-first and memory-before-generation remain invariants unless product scope fundamentally changes.
