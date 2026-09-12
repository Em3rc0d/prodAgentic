# MK1-R2 — Local Release Stabilization Build Record

Status: **IMPLEMENTATION STABILIZATION IN PROGRESS / NOT CERTIFIED**

## Authority

Rejected predecessor:
`0521ec157f02d0acd7a0a779a4f34c2c18678f1b`

Historical certification PR:
`#62` — **REJECTED / MUST NOT MERGE**

Working branch:
`mk1-r2-candidate-2-stabilization`

The exact next release-candidate SHA is intentionally not embedded in this tracked file. Candidate identity is the immutable PR head plus exact-head workflow receipts. Any tracked mutation after candidate PR creation supersedes that candidate and requires a fresh candidate PR/SHA under the repository candidate law.

## Scope

This stabilization is constrained to release defects demonstrated by Candidate 1 evidence. It does not reopen product architecture, S0-S12 ownership, Phase H cutover semantics, VisualSpec contracts, RendererPort ownership, Approval authority, or ManualExport authority.

Permitted changes:
- test correction where the assertion contradicted the already-frozen persistence representation;
- semantics-preserving adapter hardening at the existing internal RendererPort boundary;
- release-certificate observability/evidence hardening;
- regression tests for the demonstrated failure class.

Architecture changes are out of scope and would stop this build under `WORK_EXECUTION_DIRECTIVE.md`.

## Candidate 1 evidence incorporated

### Backend / Phase H

`PHASE-H Production Cutover Cert`:
- rollback/config contract: PASS;
- fresh production smoke: PASS;
- Mongo/Redis restart readiness: PASS;
- integrated authority regression: FAIL (`48 passed / 1 failed`).

Root cause confirmed from uploaded workflow evidence:
`ProfileVersion.accepted_at` domain datetime was compared directly with its intentionally canonical ISO string in raw Mongo storage.

### Horizontal R2 journey

`MK1-R2 Demo Journey Cert`:
- isolated Compose startup: PASS;
- `READY_DEMO`: PASS;
- Profile creation: PASS;
- batch planning: PASS;
- text production: PASS;
- VisualSpec production: PASS;
- render HTTP boundary: FAIL `502`;
- Review/Approval/ManualExport: NOT REACHED;
- restart/persistence journey: NOT REACHED.

S5-CERT separately proved the same renderer image can launch Chromium and generate real owned PNG goldens. Therefore the release defect is treated as an integration-boundary failure, not as permission to replace or redesign the certified renderer.

## Stabilization changes

1. Correct the real-Mongo crash-recovery assertion to compare the canonical persisted timestamp representation without changing persistence semantics.
2. Make internal RendererPort HTTP independent of ambient proxy variables (`trust_env=False`).
3. Preserve bounded renderer diagnostics in backend logs without exposing implementation details through the public route.
4. Add a regression test proving proxy variables cannot intercept internal RendererPort traffic and retry semantics remain intact.
5. Add an explicit backend-container → renderer health proof to R2-CERT.
6. Preserve bounded `GenerationRun.failure` evidence plus Compose logs for failed horizontal journeys.

## Invariants preserved

- exact ProfileVersion digest inputs remain immutable;
- no historical ProfileVersion is rewritten during recovery;
- retryable render failure remains retryable and does not falsely advance authority;
- renderer remains isolated behind `RendererPort`;
- renderer output remains product-owned through `AssetStore` and SHA-256 lineage;
- S5 still stops before QA/Review/Approval authority;
- user-facing renderer failures remain fail-closed;
- no deployment/provider success is inferred from repository tests.

## Required evidence before candidate freeze

The next exact SHA must pass all repository-required gates plus the R2 horizontal gate. At minimum:

```text
CI backend-test                         PASS
CI frontend-test                        PASS
UI-01-CERT browser                      PASS
Docker Compose Local                    PASS
S3..S12                                 PASS
PHASE-H authority-rollback-contracts    PASS
PHASE-H fresh-production-smoke          PASS
R2 backend→renderer transport           PASS
R2 Profile→Export horizontal journey    PASS
R2 backend restart                      PASS
R2 approval/assets persistence          PASS
tracked checkout clean                  PASS
```

Phase H remains governed by its stricter `13/13 pre-merge + 13/13 post-merge` rule. The R2 horizontal gate is additional release evidence, not a substitute for those certificates.

## Merge rule

No merge is authorized until one immutable PR head passes the full required matrix. Merge must use `expected_head_sha`. Post-merge certification must run on the resulting `main` SHA before MK1-R2 may be declared `FULL FUNCTIONAL / CERTIFIED / CLOSED`.
