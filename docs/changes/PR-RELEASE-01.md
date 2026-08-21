# PR-RELEASE-01 — Deterministic release certification

## Purpose

Certify the complete trusted product lifecycle without confusing an injected provider with external LinkedIn proof.

## First closed slice

The release harness proves:

1. A generated `ContentRun` and versioned profile snapshot survive beyond the generation session.
2. The run can be reopened with complete stage lineage.
3. Human editing changes final copy without rewriting generated provenance.
4. Explicit approval freezes the exact reviewed content and bundle digest.
5. Scheduling binds to that immutable approval.
6. The due worker uses the shared `PublicationCoordinator`.
7. A second worker pass cannot publish the same scheduled run again.
8. Final state contains `PUBLISHED`, completed schedule evidence, external post identity, and the approved bundle digest.

## Evidence boundary

The injected publisher returns a deterministic test URN. This certifies prodAgentic's orchestration, lifecycle, atomic claim, and evidence persistence. It does **not** prove that LinkedIn accepted or displayed a real post.

## Remaining release proof

- Execute the authenticated lifecycle through HTTP rather than direct route calls.
- Exercise a real MongoDB process and restart/reopen behavior.
- Include a persisted rendered visual and byte-digest verification in the release journey.
- Run the complete clean-environment CI gate.
- Perform one separately authorized real LinkedIn smoke publication as the final external gate.
