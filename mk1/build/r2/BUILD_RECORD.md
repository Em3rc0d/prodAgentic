# MK1-R2 — Local Release Stabilization Build Record

Status: **FULL FUNCTIONAL / CERTIFIED / CLOSED**

> Closure is evidence-bound. The operational release was proven on `main@d205494cb803e97fcad9e9ce5f72ccb1a70b2ce9`. This retrospective documentation seal changes no runtime behavior and is valid only if its own exact-head matrix and the resulting exact-`main` post-merge matrix also complete green. Any failed seal gate reopens documentation closure without retroactively relabeling a failed SHA.

## Authority

Rejected immutable candidates:
- Candidate 1 `0521ec157f02d0acd7a0a779a4f34c2c18678f1b` — PR `#62` — **REJECTED / IMMUTABLE**.
- Candidate 2 `32d8c3e875c3354426dde82d4b7a633a8214ec61` — PR `#63` — **REJECTED / IMMUTABLE**.

Accepted runtime candidate:
- Candidate 3 `a653ed9f838e09c6cbfbc7bce39826482c94901a` — PR `#64` — **PRE-MERGE CERTIFIED / MERGED**.

Certified operational merge:
- `main@d205494cb803e97fcad9e9ce5f72ccb1a70b2ce9` — **POST-MERGE CERTIFIED**.

## Scope closed

The release stabilization remained constrained to demonstrated defects. It did not reopen product architecture, S0-S12 ownership, Phase H cutover semantics, VisualSpec contracts, RendererPort ownership, Approval authority, or ManualExport authority.

The final corrections were semantics-preserving:
1. corrected the ProfileVersion crash-recovery assertion to compare canonical persisted timestamp representation;
2. hardened internal Backend→Renderer HTTP against ambient proxy interception while preserving the existing RendererPort boundary;
3. preserved bounded renderer diagnostics without exposing unsafe public details;
4. preserved immutable `AssetV1` / `RenderResultV1` digest inputs by storing their high-precision timestamps canonically instead of allowing BSON millisecond truncation;
5. added real-Mongo S5 regression coverage using non-zero microseconds;
6. strengthened the horizontal R2 certificate so release evidence spans the complete user-visible journey and restart/persistence authority.

## Root-cause closure

Candidate 1 proved the release was not ready: horizontal render failed and Phase-H inherited regression was red.

Candidate 2 removed the false-red ProfileVersion assertion and proved direct Backend→Renderer transport, but the horizontal journey still failed with terminal `S5_RENDER_INTEGRITY_FAILED`.

The remaining root cause was high-precision timestamp loss in immutable render metadata: S5 digests included microseconds while BSON datetime persisted only millisecond precision. Immediate authoritative readback therefore recomputed a different digest. Candidate 3 changed immutable render metadata persistence to canonical JSON timestamp representation and retained fail-closed digest verification. No rejected historical record was rewritten.

## Candidate 3 exact-head evidence

Candidate 3 exact head `a653ed9f838e09c6cbfbc7bce39826482c94901a` passed the complete pre-merge matrix, including:

```text
CI frontend-test                        PASS
CI backend-test                         PASS
production backend image build/smoke   PASS
UI-01 desktop + mobile browser          PASS
Docker Compose Local                    PASS
S3..S12                                 PASS
PHASE-H authority-rollback-contracts    PASS
PHASE-H fresh-production-smoke          PASS
S5 real-Mongo high-precision timestamps PASS
R2 backend→renderer transport           PASS
R2 Profile→Export horizontal journey    PASS
R2 backend restart                      PASS
R2 approval/assets persistence          PASS
tracked checkout clean                  PASS
```

The R2 horizontal run proved the actual sequence:

`Profile → Batch → Text → VisualSpec → Chromium Render → QA → Review → Approval → ManualExport → backend restart → recovered Approval + carousel + authoritative persistence`.

## Exact-main post-merge evidence

PR `#64` was merged with `expected_head_sha=a653ed9f838e09c6cbfbc7bce39826482c94901a`.

Resulting merge SHA:
`d205494cb803e97fcad9e9ce5f72ccb1a70b2ce9`.

On that exact `main` SHA:
- all **14/14 push workflows** completed with `success`;
- all **17/17 check-runs** completed with `success`;
- `CI` run `34707326116` passed frontend, backend and `UI-01-CERT browser`;
- `MK1-R2 Demo Journey Cert` run `34707326123` passed the full horizontal journey;
- S5 real renderer/Mongo integrity certification passed;
- Phase H both post-merge jobs passed;
- Docker Compose Local passed;
- S3 through S12 passed.

No failed, skipped-as-evidence or pending required post-merge gate remains.

## Invariants preserved

- exact ProfileVersion, AssetV1 and RenderResultV1 digest inputs remain immutable;
- no historical immutable record is silently rewritten during recovery;
- retryable render failure remains retryable and cannot falsely advance authority;
- digest mismatch remains terminal/fail-closed;
- renderer remains isolated behind `RendererPort`;
- renderer output remains product-owned through `AssetStore` and SHA-256 lineage;
- S5 still stops before S6/S7 authority;
- public renderer failures remain safe and fail-closed;
- repository certification does not falsely claim an external provider publication or hosting deployment.

## Operational conclusion

Within the certified repository/local-release boundary, MK1-R2 is:

**FULL FUNCTIONAL / CERTIFIED / CLOSED**.

The provider-independent certified distribution path remains ManualExport. Real external LinkedIn publication, live provider analytics reads or a hosting deployment remain separate external boundaries and must only be claimed when independently authorized and evidenced.
