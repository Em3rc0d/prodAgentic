# MK1 Architecture Decision Records

Accepted ADRs override lower-authority design brainstorming when conflicts exist.

Format:

```text
Status
Date
Context
Decision
Consequences
Alternatives considered
Revisit conditions
```

## Index

- ADR-0001 — Modular monolith + separately runnable workers
- ADR-0002 — Split MK0 ContentRun responsibilities
- ADR-0003 — Tenant scope from the first MK1 entity
- ADR-0004 — Mongo authority + Redis Streams transport + Mongo outbox
- ADR-0005 — Batch-first planning with Editorial Memory and Novelty
- ADR-0006 — Versioned structured agent contracts
- ADR-0007 — VisualSpec intermediate representation
- ADR-0008 — Immutable human approval bundle
- ADR-0009 — At-least-once publication with reconciliation
- ADR-0010 — Capability-aware adapters and manual fallback
- ADR-0011 — Snapshot analytics with bounded learning
- ADR-0012 — Chromium/Playwright as first deterministic renderer adapter
