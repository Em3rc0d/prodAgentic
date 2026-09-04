# ADR-0008 — Immutable human approval bundle

**Status:** ACCEPTED  
**Date:** 2026-09-04

## Context

MK0 proved that generation completion must not equal publish authority and that exact text/visual bytes can be digest-bound.

## Decision

MK1 V1 requires explicit authenticated human approval of one exact `ContentRevision`. Approval is immutable and binds Profile/plan/research/content/VisualSpec/QA digests plus exact Asset SHA-256 values into `ApprovalBundleV2`.

## Consequences

- publisher never reads mutable draft authority;
- changes after approval create a new revision/approval;
- human approval remains a deliberate friction at the irreversible boundary.

## Revisit

Policy-based auto-approval may be explored later but must create equally strong immutable authority/evidence and remain an explicit user-controlled autonomy mode.
