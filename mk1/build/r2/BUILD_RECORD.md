# MK1-R2 — Local Release Stabilization Build Record

Status: **IMPLEMENTATION STABILIZATION IN PROGRESS / NOT CERTIFIED**

## Authority

Rejected candidates:
- Candidate 1 `0521ec157f02d0acd7a0a779a4f34c2c18678f1b` — PR `#62` — **REJECTED / IMMUTABLE**.
- Candidate 2 `32d8c3e875c3354426dde82d4b7a633a8214ec61` — PR `#63` — **REJECTED / IMMUTABLE**.

Working branch:
`mk1-r2-candidate-3-render-integrity`

The exact next release-candidate SHA is intentionally not embedded in this tracked file. Candidate identity is the immutable PR head plus exact-head workflow receipts. Any tracked mutation after candidate PR creation supersedes that candidate and requires a fresh candidate PR/SHA under the repository candidate law.

## Scope

This stabilization is constrained to release defects demonstrated by exact-head certification evidence. It does not reopen product architecture, S0-S12 ownership, Phase H cutover semantics, VisualSpec contracts, RendererPort ownership, Approval authority, or ManualExport authority.

Permitted changes remain semantics-preserving fixes, regression coverage, observability/evidence hardening and persistence corrections required to preserve already-defined immutable hash inputs. Architecture changes are out of scope and would stop this build under `WORK_EXECUTION_DIRECTIVE.md`.

## Candidate 1 result

Candidate 1 established that Docker/READY_DEMO, text production and VisualSpec production worked, while backend/Phase-H regression and the horizontal render path remained red. S5-CERT independently proved the real Chromium renderer image could generate owned PNG goldens.

The Phase-H/backend regression was traced to a test representation mismatch for `ProfileVersion.accepted_at`; storage intentionally preserves the canonical JSON timestamp to avoid BSON precision loss. Candidate 2 fixed that assertion without changing persistence authority.

## Candidate 2 result

Candidate 2 exact head `32d8c3e...` proved:
- CI frontend PASS;
- backend tests PASS;
- production backend image build/smoke PASS;
- Phase H authority/rollback contracts PASS;
- Phase H fresh-production restart smoke PASS;
- S3/S4/S6/S7/S8/S9/S10/S11/S12 PASS as observed in the matrix;
- Docker Compose Local PASS;
- R2 stack + `READY_DEMO` PASS;
- backend-container → renderer direct health transport PASS.

The horizontal journey still failed during `Produce carousel approve and export`. Retained evidence recorded `S5_RENDER_INTEGRITY_FAILED`, not a RendererPort transport failure. This disproved ambient proxy interception as the root cause.

Code/evidence reconciliation identified the remaining defect: S5 immutable `AssetV1` / `RenderResultV1` digests include timestamps, while their Mongo repository persisted Python datetimes through BSON, truncating non-zero microseconds. Existing S5 real-Mongo coverage used a zero-microsecond fixture and therefore did not exercise the invariant.

## Candidate 3 stabilization changes

1. Preserve `AssetV1` metadata with `model_dump(mode="json")` before Mongo insertion so `created_at` remains exactly the canonical digest input.
2. Preserve `RenderResultV1` metadata with `model_dump(mode="json")`, including `started_at`, `completed_at` and nested asset timestamps.
3. Keep Pydantic model validation as the typed read/rehydration boundary.
4. Change the real-Mongo S5 fixture to a non-zero-microsecond timestamp.
5. Assert raw Mongo timestamps equal each model's canonical JSON representation before restart/readback checks.
6. Preserve historical mismatched rows fail-closed; no rejected-candidate history is rewritten.
7. Retain Candidate 2 transport hardening and R2 evidence probes because they improve deterministic internal networking and observability without changing authority.

## Invariants preserved

- exact ProfileVersion, AssetV1 and RenderResultV1 digest inputs remain immutable;
- no historical immutable record is silently rewritten during recovery;
- retryable render failure remains retryable and cannot falsely advance authority;
- digest mismatch remains terminal/fail-closed;
- renderer remains isolated behind `RendererPort`;
- renderer output remains product-owned through `AssetStore` and SHA-256 lineage;
- S5 still stops before S6/S7 authority;
- public renderer failures remain safe and fail-closed;
- no deployment/provider success is inferred from repository tests.

## Required evidence before merge

The next frozen exact SHA must pass all repository-required gates plus the R2 horizontal gate:

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

No skipped downstream step counts as evidence. Phase H remains governed by its stricter `13/13 pre-merge + 13/13 post-merge` law. The R2 horizontal gate is additional release evidence, not a substitute.

## Merge rule

No merge is authorized until one immutable PR head passes the complete required matrix. Merge must use `expected_head_sha`. Post-merge certification must run on the resulting exact `main` SHA before MK1-R2 may be declared `FULL FUNCTIONAL / CERTIFIED / CLOSED`.
