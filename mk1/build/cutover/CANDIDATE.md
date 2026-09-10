# PHASE H CANDIDATE — Production Cutover

Status: **IMPLEMENTATION COMPLETE / CERTIFICATION PENDING**

Base authority: `main@f71c44eda4cf9769c9eb216469fbcd741e789220`
Formalization authority: `85d27541e566d8f8124799ca61e0e52016f4983a`

## Candidate identity law

The exact Phase H candidate SHA is intentionally not embedded in this tracked file. Authoritative identity is the immutable PR head plus workflow receipt and `expected_head_sha` merge gate.

Any tracked mutation after candidate PR creation rejects that candidate and requires a new candidate SHA/PR.

## Frozen cutover authority

```text
MK1_PRODUCTION_CUTOVER=true
        ↓
all certified MK1 V1 flags required
        ↓
MK0 mutation/generation/publication HTTP authority = RETIRED (410)
MK0 historical GET authority = PRESERVED
MK0 scheduler = DISABLED while MK1_PUBLISH_WORKER owns publication
        ↓
MK1 S0–S12 path = sole new-content authority
```

## Release candidate proof

Phase H adds a disposable production-mode environment that validates:

- production configuration startup;
- all MK1 cutover flags;
- Mongo + Redis durability;
- publish/analytics workers alive;
- MK0 scheduler disabled;
- auth boundary;
- legacy writes rejected;
- historical reads preserved;
- production frontend artifact built with publishing/analytics flags;
- readiness remains green after Mongo/Redis/backend restart;
- rollback is configuration-only and tested separately.

## External gates

```text
LinkedIn public publish        NOT EXERCISED — explicit operator authorization required
LinkedIn live analytics read  NOT EXERCISED — provider capability/authorization dependent
ManualExport                  certified provider-independent distribution path (S8)
```

No provider success is inferred from mocks/contracts.

## Certification gate

Require one immutable candidate to pass exactly:

```text
CI
Docker Compose Local
S3 Structured Agent Cell Cert
S4 VisualSpec V1 Cert
S5 Renderer + AssetStore Cert
S6 QA + Recovery Cert
S7 Review + Approval V2 Cert
S8 Manual Export Package Cert
S9 Redis Streams + Mongo Outbox Cert
S10 Calendar + LinkedIn Publication Cert
S11 Analytics Snapshots Cert
S12 PerformanceSummary + Planner Learning Cert
PHASE-H Production Cutover Cert
```

= **13/13 pre-merge** and **13/13 post-merge** on exact SHAs.

MK0 cleanup is explicitly out of scope until the rollback window expires.
