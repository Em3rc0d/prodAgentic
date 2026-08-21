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

## Second closed slice

- Authenticated HTTP boundary proves login, session cookie, CSRF, reopen, edit, approval, and scheduling through the real routers.
- Real MongoDB 7 CI service proves approved profile/run/schedule evidence survives client-process replacement.
- The visual release journey approves a persisted byte digest, uploads exactly those bytes through the injected provider, and stores image/post evidence.
- Tampering after approval stops before any external request.

## Remaining release proof

- Run the complete clean-environment CI gate.
- Perform one separately authorized real LinkedIn smoke publication as the final external gate.
