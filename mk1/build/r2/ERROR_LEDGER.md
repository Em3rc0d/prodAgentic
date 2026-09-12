# MK1-R2 — Release Stabilization Error / Near-Miss Ledger

Status: **CLOSED / HISTORICAL / APPEND-ONLY**

Policy: material CI failures, false greens, superseded candidates, root-cause evidence and recovery decisions are retained. A rejected SHA is never rewritten into a certified candidate.

## R2-E001 — Candidate 1 failed the horizontal release journey

Candidate:
`0521ec157f02d0acd7a0a779a4f34c2c18678f1b`

Observed evidence:
- PR `#62` remained unmerged.
- `MK1-R2 Demo Journey Cert` run `34551049264`, job `103113839654`, failed at `Produce carousel approve and export`.
- Docker Compose startup and `/health/ready = READY_DEMO` passed.
- Profile, batch, text production and VisualSpec production completed successfully.
- `POST /api/content-revisions/{revision_id}/render` returned HTTP `502`.
- Approval, ManualExport and the restart/persistence half of the horizontal journey were therefore not exercised.

Decision:
Candidate 1 is **REJECTED / IMMUTABLE**. It is not eligible for rerun-as-certification after tracked changes.

Status: HISTORICAL REJECTION PRESERVED.

## R2-E002 — Phase H / backend false-red caused by timestamp representation mismatch in the test

Observed evidence:
`PHASE-H Production Cutover Cert` run `34551049412` passed the explicit rollback/config laws and fresh-production smoke, but its integrated authority regression produced `48 passed / 1 failed`.

Exact failing assertion:
`test_real_mongodb_profile_update_recovers_interrupted_version_pointer` compared:
- the rehydrated domain `datetime` in `ProfileVersion.accepted_at`; against
- the raw Mongo document ISO string intentionally persisted by `model_dump(mode="json")`.

Why the storage representation is intentional:
ProfileVersion hash inputs preserve exact timestamp precision. BSON datetime conversion truncates precision, so the immutable version payload is stored canonically as JSON-compatible ISO text and rehydrated by Pydantic when read through repository authority.

Correction:
Compare `recovered.version.model_dump(mode="json")["accepted_at"]` to the raw persisted ISO value. Production persistence semantics are unchanged.

Status: REPAIRED / VERIFIED BY FRESH CI + PHASE-H.

## R2-E003 — Horizontal RendererPort failure was opaque at the integration boundary

Observed evidence:
S5-CERT independently built the real Playwright renderer and generated real Chromium golden PNGs successfully, while the R2 Compose journey returned HTTP `502`. Candidate 1 renderer logs contained only the startup line and the backend adapter intentionally collapsed renderer/transport failures to a safe public error.

Inference boundary:
The evidence proved this was not a generic inability to package or launch Chromium. Candidate 1 evidence alone was insufficient to distinguish an internal transport/proxy failure from a renderer response/contract failure.

Corrections in stabilization:
- internal Backend→Renderer HTTP uses `trust_env=False`, preventing ambient `HTTP_PROXY` / `HTTPS_PROXY` settings from hijacking the internal Docker/service-name boundary;
- adapter logs bounded renderer-owned diagnostics while the public API remains fail-closed and non-sensitive;
- a regression test proves ambient proxy configuration is ignored and retryable renderer failures retain retry semantics;
- R2-CERT explicitly probes Backend→Renderer health from inside the backend container before the browser journey;
- R2-CERT preserves bounded `GenerationRun.failure` evidence and full Compose logs on every run.

Status: HARDENED / TRANSPORT HYPOTHESIS DISPROVED AS ROOT CAUSE BY CANDIDATE 2.

## R2-E004 — A green slice certificate is not sufficient release evidence

Observed:
S3-S12 slice certificates were mostly green on Candidate 1, including real S5 Chromium goldens, while the user-visible horizontal journey still failed before Review.

Correction:
R2 release certification adds a horizontal exact-SHA gate:
`Profile → Batch → Text → VisualSpec → Render → QA → Review → Approval → ManualExport → backend restart → persisted approval/assets`.

Status: REQUIRED RELEASE GATE / VERIFIED GREEN ON ACCEPTED CANDIDATE AND EXACT MAIN.

## R2-E005 — Candidate 2 isolated the real S5 Mongo render-integrity defect

Candidate:
`32d8c3e875c3354426dde82d4b7a633a8214ec61`

Observed evidence:
- PR `#63` remained unmerged and was closed after the exact-head R2 gate failed.
- Phase H both jobs passed, including the previously failing integrated authority regression and the fresh production restart smoke.
- repository backend tests, production backend image build/smoke, frontend tests/build, Docker Compose Local and the observed S3/S4/S6/S7/S8/S9/S10/S11/S12 gates passed.
- R2 `READY_DEMO` passed.
- backend-container → renderer `/health` proof passed with `DIRECT_INTERNAL_NO_ENV_PROXY`.
- the horizontal `Produce carousel approve and export` step still failed.
- retained `generation-failures.json` recorded terminal `S5_RENDER_INTEGRITY_FAILED` at `RENDERING`, not a retryable RendererPort failure.
- renderer logs contained normal startup and no renderer execution error associated with the failed journey.

Root cause:
`MongoRenderingRepository.save_asset()` and `save_render_result()` computed canonical digests from `AssetV1` / `RenderResultV1`, then persisted those models with Python `datetime` objects via `model_dump()`. PyMongo/BSON stores datetime only at millisecond precision. Real rendering creates timestamps with non-zero microseconds, so an immediate authoritative read reconstructs a semantically similar but byte-different timestamp. Recomputing the immutable metadata/result digest therefore fails closed. The existing real-Mongo S5 test used a timestamp with zero microseconds and masked the defect.

Correction:
- persist immutable `AssetV1` and `RenderResultV1` metadata with `model_dump(mode="json")`, preserving exact canonical timestamp strings used by the digest;
- keep Pydantic as the typed rehydration boundary on reads;
- change the real-Mongo S5 gate to use a non-zero-microsecond timestamp and assert the raw stored timestamp equals the model's canonical JSON representation;
- do not rewrite historical rows from rejected candidates; malformed/digest-mismatched historical render metadata continues to fail closed.

Status: REPAIRED BY CANDIDATE 3 / VERIFIED BY FULL MATRIX.

## R2-E006 — Candidate 3 closed the release and exact-main post-certification

Accepted candidate:
`a653ed9f838e09c6cbfbc7bce39826482c94901a`

PR:
`#64`

Observed pre-merge evidence:
- complete Candidate 3 workflow matrix completed green on the immutable PR head;
- S5 real-Mongo regression with non-zero microseconds passed;
- real Playwright/Chromium renderer and owned PNG verification passed;
- R2 full horizontal journey passed through Render, QA, Review, Approval and ManualExport;
- backend restart passed over persisted Mongo/assets;
- post-restart Approval and carousel recovery passed;
- tracked checkout remained clean;
- Phase H both jobs passed;
- UI desktop/mobile passed.

Merge control:
PR `#64` was merged using `expected_head_sha=a653ed9f838e09c6cbfbc7bce39826482c94901a`.

Resulting exact `main` SHA:
`d205494cb803e97fcad9e9ce5f72ccb1a70b2ce9`.

Observed post-merge evidence on that exact SHA:
- **14/14 push workflows completed with `success`**;
- **17/17 check-runs completed with `success`**;
- CI run `34707326116` passed frontend, backend and UI-01 desktop/mobile;
- R2 Demo Journey run `34707326123` passed the complete user-visible + restart/persistence certificate;
- Phase H both post-merge jobs passed;
- Docker Compose Local passed;
- S3 through S12 passed;
- no required workflow remained failed, pending or skipped-as-evidence.

Decision:
The demonstrated Candidate 1/2 release defects are closed without rewriting rejected history. Within the certified repository/local-release boundary, MK1-R2 reached `FULL FUNCTIONAL / CERTIFIED / CLOSED` on the evidence above.

External-boundary note:
This does not claim a real LinkedIn publication, live provider analytics read or hosting deployment. ManualExport is the provider-independent certified distribution path.

Status: RELEASE DEFECT LEDGER CLOSED. FUTURE DEFECTS REQUIRE NEW ENTRIES; HISTORICAL ENTRIES REMAIN IMMUTABLE.
