# MK1 Quarries

A quarry is a bounded investigation whose answer is not yet authoritative.

Use quarries for questions that require experiments, external provider research, calibration, dataset work, or multiple competing approaches.

## Quarry contract

Every quarry must define:

```text
question
why it matters
scope
inputs/evidence
hypotheses
experiment or analysis method
result
confidence
recommended promotion target
revisit condition
```

## States

- `OPEN` — question exists, work not sufficient.
- `MINING` — evidence/experiments actively collected.
- `ANSWERED` — recommendation exists but is not yet promoted.
- `PROMOTED` — accepted result moved into design/architecture/ADR.
- `PARKED` — deliberately deferred without blocking current build slices.

## Initial quarry families

- `novelty/` — thresholds, taxonomy coverage and collision calibration.
- `visuals/` — render strategies, format quality and layout benchmarks.
- `publishing/` — external platform capability research.
- `analytics/` — useful normalized metric features and learning boundaries.

Quarries never become a back door for changing architecture. Promotion is explicit.
