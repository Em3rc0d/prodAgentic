# Q-ANALYTICS-01 — Cross-platform metric normalization

**State:** PARKED (non-blocking)

## Question

Which metrics are semantically comparable enough across providers to normalize, and which must remain provider-specific?

## Inputs

- official metric definitions;
- provider snapshots from S11;
- missing-data/freshness behavior;
- user decisions that Analytics should support.

## Method

Create a semantic mapping table with confidence and explicit non-equivalences. Validate PerformanceSummary usefulness against planning decisions without causal overclaim.

## Current architecture answer

MetricSnapshot stores raw available + only defensible normalized values. Missing remains unavailable. PerformanceSummary carries confidence/sample size.

## Promotion

Update normalization policy/schema version and contract fixtures; do not rewrite historical snapshots.
