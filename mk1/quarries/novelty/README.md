# Q-NOVELTY-01 — Similarity and cooldown calibration

**State:** PARKED (non-blocking)

## Question

What taxonomy coverage, semantic thresholds and Profile-specific cooldown values minimize meaningful repetition without suppressing legitimately fresh angles?

## Inputs

- GD-01/02/03 novelty benchmark pairs;
- human BLOCK/REWRITE/WARNING/PASS labels;
- real override/rejection telemetry after S2.

## Method

Compare lexical/taxonomy/embedding/angle/creative signals; build precision/recall confusion matrices against human labels; calibrate thresholds per domain/Profile class only when sample supports it.

## Current architecture answer

Thresholds are versioned policy. Default cooldown bands are sufficient to begin S2; exact semantic threshold is not frozen as a universal constant.

## Promotion

Update `arch/EDITORIAL_ENGINE.md` policy version and tests. Architecture layers remain unchanged unless evidence shows a layer is invalid.
