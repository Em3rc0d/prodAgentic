# ADR-0011 — Snapshot analytics with bounded learning

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

Mutable counters lose temporal/provider evidence, while feeding raw engagement directly into prompts invites overfitting and repetitive content.

## Decision

Store append-only MetricSnapshots. Build normalized `PerformanceSummaryV1` features with sample size/confidence. Planner uses performance only after brand, safety, novelty, diversity and quality constraints.

## Consequences

- historical metric evolution is inspectable;
- missing data is not confused with zero;
- learning remains bounded and explainable.

## Revisit

More advanced experiments/causal optimization may extend summaries but cannot bypass higher-priority policy without a new ADR.
