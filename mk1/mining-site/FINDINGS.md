# MK1 Repository Findings

Audit date: **2026-09-04**

## F1 — MK0 has strong safety invariants hidden inside a weak aggregate boundary

`ContentRun` successfully accumulated evidence and lifecycle controls, but generation, review, approval, schedule and publication are too tightly coupled for the next product shape.

**Implication:** preserve invariants, split responsibilities.

## F2 — MK0 is piece-first, MK1 must be batch-first

The current orchestrator receives an idea and executes production stages for that idea. It has no authoritative batch strategy or current-batch collision model.

**Implication:** `BatchPlanner` becomes the upstream application service and `ContentItem` becomes the conceptual post.

## F3 — Profile snapshots are already a proven primitive

Historical runs remain associated with the version used at generation time.

**Implication:** MK1 extends Profile semantics rather than replacing versioned snapshots.

## F4 — Approval/publishing evidence is worth carrying forward nearly unchanged semantically

The existing flow correctly treats approval as explicit authority and verifies exact approved bytes before an external post.

**Implication:** make Approval first-class and keep digest binding.

## F5 — Redis is new architecture

No Redis library exists in the current backend dependency baseline.

**Implication:** Redis introduction must have its own ADR, failure semantics, tests and feature flag; it cannot be described as a refactor of an existing queue.

## F6 — Existing UI reflects implementation history

Separate Library, Publishing and Scheduling surfaces mirror backend slices.

**Implication:** MK1 navigation should map to user jobs, not database/domain modules.

## F7 — Visual intent is under-modeled

MK0 owns rendered assets but the visual agent primarily produces a prompt, leaving layout/format semantics implicit.

**Implication:** VisualSpec is required before renderer expansion.

## F8 — Original product scope is obsolete as a top-level contract

The historical context frames the product as a LinkedIn technical-content engine for one operator.

**Implication:** MK1 documentation must be independently understandable as a multi-Profile content OS while preserving LinkedIn as the first certified automatic adapter.
