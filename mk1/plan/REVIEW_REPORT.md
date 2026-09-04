# MK1 Design Freeze Self-Review Report

**Review date:** 2026-09-04  
**Scope:** repository diff from MK0 baseline `aa64a49...` through MK1 design-freeze branch  
**Result:** PASS after corrections below

## Review dimensions

- product scope vs UX;
- UX vs domain entities;
- domain vs state machines;
- editorial memory vs multi-destination distribution;
- agent authority vs structured contracts;
- VisualSpec vs approval asset identity;
- approval vs editing/invalidation;
- schedule/publication vs Redis transport;
- publication uncertainty vs retry rules;
- analytics vs novelty/safety priority;
- tenancy/security vs migration;
- plan slices vs test/certification coverage;
- repository generation/folder semantics.

## Findings corrected

### SR-01 — ContentItem distribution-state conflation

**Severity:** BLOCKING if left unresolved.

Initial draft showed `ContentItem` progressing through `SCHEDULED -> PUBLISHING -> PUBLISHED`. This conflicts with capability-aware multi-destination distribution because one Approval can be scheduled/published to several targets with different states.

**Correction:** ContentItem now owns editorial lifecycle only through Approval/revision states. Schedule and Publication own destination-specific distribution states. Any ContentItem distribution summary is derived/read-model data.

Files corrected:

- `arch/DOMAIN_MODEL.md`
- `arch/STATE_MACHINES.md`

### SR-02 — Design graph closed-node count mismatch

**Severity:** documentation integrity.

Detailed graph contains 70 critical nodes, while summary incorrectly stated 48.

**Correction:** summary now states 70 CLOSED / 0 OPEN / 0 REVISIT.

### SR-03 — Multi-platform Editorial Memory double-count risk

**Severity:** semantic.

A single approved revision published to multiple platforms could otherwise appear as several different ideas in memory.

**Correction:** memory normalization deduplicates the underlying editorial revision/concept; only materially different platform derivatives become distinct entries.

### SR-04 — Manual distribution connection optionality

**Severity:** model consistency.

Publication model originally implied `connection_id` was always present while ManualExport deliberately supports unsupported/unconnected channels.

**Correction:** Publication connection is optional where no automatic external account exists; automatic adapter publication still requires its connection/capability authority.

### SR-05 — MK0 folder-generation discoverability

**Severity:** repository usability.

MK0 historical source existed only in legacy root paths, while the new generation method promises a common lifecycle vocabulary.

**Correction:** add MK0 lifecycle-directory indexes that map each new vocabulary area to the historical source/evidence without moving or rewriting MK0 code.

## Non-blocking observations

- Exact semantic novelty threshold remains a calibration quarry by design; stable policy interface exists.
- Additional automatic social adapters remain capability quarries; ManualExport closes the V1 product job.
- Motion/video remains out of static V1; VisualSpec can version later.
- Existing single-admin auth is not mistaken for multi-tenancy; S0 introduces bootstrap tenant scope before commercial auth expansion.

## Contradiction check after correction

No remaining build-critical contradiction found across:

```text
product -> UX -> domain -> contracts -> visual -> QA -> approval
-> data -> Redis/outbox -> publication -> analytics -> tests
```

## Review conclusion

The design baseline is internally consistent enough to enter implementation once it is accepted/merged as the canonical MK1 baseline. The remaining merge action is repository governance, not an unresolved design node.
