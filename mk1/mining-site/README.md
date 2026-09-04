# MK1 Mining Site

The mining site is the evidence intake layer.

It answers: **What did we actually observe, where did it come from, and how confident are we?**

It must not silently turn observations into architecture.

## Rules

1. Every important observed fact receives an evidence ID in `EVIDENCE_LEDGER.md`.
2. Evidence points to repository files, accepted product input, tests, provider documentation, or measured runtime output.
3. `OBSERVED` means directly supported; `INFERRED` means derived.
4. External facts that may change must record the observation date/version.
5. Raw evidence does not override accepted MK1 design decisions; it may trigger a revisit condition.
6. New research questions are opened in `../quarries/`, not solved by editing canonical architecture ad hoc.

## Promotion path

```text
source/evidence
    -> mining-site finding
    -> quarry when analysis is needed
    -> brainstorming option
    -> design/arch decision
    -> ADR when architectural
    -> plan/build/test
```
