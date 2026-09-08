# S5 — Renderer + AssetStore — Error / Near-Miss Ledger

Status: **OPEN / APPEND-ONLY DURING BUILD**

Policy: every material implementation error, false-green, architectural near-miss, superseded candidate, CI failure and recovery decision is retained here. Do not rewrite history to make S5 look cleaner than it was.

## E001 — Treating S5 as “just screenshot HTML”

Risk:
A browser screenshot can look correct while violating authority if critical copy is retyped, generated, or resolved from a mutable source.

Correction:
Renderer input must be derived from the exact persisted `ContentSpecV1` and certified `VisualSpecV1` bound to the `ContentRevision`. Unknown copy refs fail before Chromium execution. `render_input_digest` binds the resolved immutable payload.

Status: PREVENTED AT BUILD ENTRY.

## E002 — Putting Chromium inside S4

Risk:
S4 is already certified as visual intent only. Reopening S4 to execute renderer bytes would blur a certified boundary and invalidate the meaning of the S4 certificate.

Correction:
S5 introduces RendererPort/AssetStore as downstream authority. S4 code is consumed, not rewritten except for a proven compatibility defect that would require explicit recertification.

Status: PREVENTED.

## E003 — Reusing legacy image/render code as MK1 authority

Risk:
Historical MK0/Commercial V1 helpers may persist files or generate visuals, but they do not automatically satisfy S5 typed lineage, exact copy refs, tenant scope, CAS, restart durability or SHA-256 authority.

Correction:
Legacy code may be mined for implementation ideas only. S5 authority is new typed contracts/adapters with explicit certification.

Status: OPEN GUARDRAIL.

## E004 — Browser dependency contaminating FastAPI production image

Risk:
Adding an implicit Chromium runtime to the backend image increases size/failure surface and can break reproducible deployment.

Current decision:
Prefer an isolated Playwright renderer adapter/runtime behind `RendererPort`, with product-owned shared AssetStore bytes. The final implementation must prove Docker/runtime packaging explicitly.

Status: DESIGN DECISION TO VERIFY IN BUILD.

## E005 — Hashing pre-owned or transient bytes

Risk:
Hashing provider output or an in-memory screenshot before the product owns the bytes can make the stored digest differ from the actual authoritative asset.

Correction:
AssetStore writes product-owned bytes, reads them back, computes SHA-256 from owned bytes, and persists that digest into AssetV1.

Status: PREVENTED BY CONTRACT.

## E006 — Path traversal / arbitrary storage keys

Risk:
Allowing renderer/client-provided paths can escape `PRODAGENTIC_ASSET_ROOT`, overwrite unrelated files, or make the DB point outside product ownership.

Correction:
AssetStore generates and validates normalized storage keys. Absolute paths, `..`, symlink escape and root escape fail closed.

Status: REQUIRED TEST.

## E007 — Partial carousel attached after mid-render crash

Risk:
Pages 0..N may be written before a failure. Attaching a partial set would violate exact page count and create a false-ready preview.

Correction:
All pages are rendered/persisted/verified first. Revision asset refs are attached only after the whole RenderResult passes exact page-count/dimension/hash checks through one optimistic-concurrency boundary.

Status: REQUIRED TEST.

## E008 — S5 claiming REVIEWABLE

Risk:
A deterministic render can still clip, overlap, mismatch semantics, or contain other visual defects. S6 owns QA and recovery.

Correction:
S5 success ends at `GenerationRun.QA` + `ContentRevision.QA_PENDING`, with `qa_report_id = null`. Preview must say `Rendered · QA pending`.

Status: PREVENTED AT BUILD ENTRY.

## E009 — Generated-image provider scope creep

Risk:
S5 could expand into provider-generated backgrounds/photos before the deterministic renderer/AssetStore path is proven, multiplying provider and safety dependencies.

Correction:
Certify composed static V1 for the three canonical formats first. Generated visual strategies may fail closed as unsupported unless a separately scoped adapter is intentionally added and certified.

Status: DEFERRED / FAIL-CLOSED.

## E010 — Treating preview as approval

Risk:
A visible image in Review could be mistaken for approved/publishable content.

Correction:
S5 preview is read-only and explicitly QA-pending. Approve remains S7 authority.

Status: PREVENTED BY UX BOUNDARY.

## E011 — Candidate freeze before golden render evidence

Risk:
A green unit suite can certify mechanics while actual output quality is poor or unreadable.

Correction:
Do not freeze S5 candidate until Content Seller, Logan and Tech golden renders exist, exact dimensions/page counts/hash evidence are captured, and desktop/mobile preview can display them.

Status: OPEN GATE.

## E012 — Documentation descendant redefining product certificate

Risk:
Later docs-only commits could be mistaken for the exact product-code certificate, repeating a known process ambiguity from earlier slices.

Correction:
S5 will preserve separate identities for candidate, receipt-head, product merge and later documentation descendant. Product certificate remains exact and immutable.

Status: PROCESS GUARDRAIL.

## E013 — Accidental unreferenced empty commit during tree assembly

Observed:
Commit `bbe4ca98beaebc5a8de240e97c10a9db87e37623` was created during low-level tree assembly but did not introduce product changes and was never moved onto `mk1/s5-renderer-assetstore`.

Risk:
Unreferenced commits can confuse lineage analysis if later mistaken for a reviewed candidate.

Correction:
The commit remains outside the branch/certification chain and is recorded here explicitly. Only commits reachable from the exact S5 branch head may become certification evidence.

Status: DOCUMENTED / NO PRODUCT EFFECT.

## E014 — Real-Mongo test commit created before advancing the branch ref

Observed:
`1ae6a5af0a4b3ccb25c2888e24feede14ebdc77a` added the S5 real-Mongo render-lineage tests, but the branch temporarily remained at `9b9ff7092f0ad1407133e78fd59799cefa7347ce`.

Risk:
Reporting a commit as branch state when the remote ref does not actually point to it creates a false evidence boundary.

Correction:
The ancestry was verified (`9b9ff709... -> 1ae6a5af...`, one fast-forward commit) and the branch was advanced with a non-forced fast-forward before subsequent S5 work.

Status: RECOVERED / HISTORY PRESERVED.

## E015 — Retryable renderer failure was incorrectly terminalized

Observed:
The initial `MongoRenderingRepository.mark_run_failed` moved every render failure to `GenerationRun.FAILED`, including `RendererPortError(retryable=True)` and retryable AssetStore failures.

Risk:
A transient Chromium/transport outage would become a terminal domain failure even though the deterministic render operation is safe to retry, contradicting the S5 recovery contract.

Correction:
Commit `c798a8db69f33d371f1af8ae26a98f29ff7f9004` changed persistence semantics: retryable failures remain in `RENDERING`, retain durable `GenerationFailureV1` evidence and `completed_at = null`; non-retryable integrity failures still transition to `FAILED`. Successful completion to `QA` clears the transient failure. Real-Mongo recovery tests were added.

Status: REPAIRED / MUST PASS S5-CERT.

## E016 — First retryable-recovery fixture leaked its temporary Mongo database on success

Observed:
The first version of `test_retryable_s5_failure_stays_recoverable_and_success_clears_failure` lacked the `finally` cleanup block that its sibling terminal-failure test already used.

Risk:
Repeated certification runs could leave temporary databases behind and make test-environment hygiene non-deterministic.

Correction:
Commit `9c5df81b6676638a68508077424e8a60b2e29afa` added unconditional database drop/client close to the first recovery test.

Status: REPAIRED.

## E017 — Golden evidence must use real Chromium bytes, not fake PNG headers

Observed:
Unit tests intentionally use minimal fake PNG headers to exercise lifecycle/integrity logic quickly. Those bytes are not visual-quality evidence.

Risk:
Treating unit-test PNG stubs as golden renders would create a false green for the S5 quality exit criterion.

Correction:
`backend/scripts/s5_generate_goldens.py` now calls the real `ChromiumRendererAdapter`, stores the returned bytes through the real `FilesystemAssetStore`, verifies read-back hashes/dimensions and emits Content Seller, Logan and Tech PNGs plus a manifest. `S5-CERT` runs this path twice against the same owned root and carries the PNGs as evidence.

Status: PREVENTED BY DEDICATED S5-CERT.

## E018 — Preview certification must use the owned golden bytes, not decorative mocks

Risk:
A UI test could pass with arbitrary placeholder images while the actual renderer output is unusable.

Correction:
The S5 browser test reads the real golden manifest, serves the exact generated Logan PNG bytes to the Review preview, checks natural image dimensions, desktop/mobile usability, page navigation, QA-pending wording and absence of approval authority.

Status: PREVENTED BY DEDICATED S5 REVIEW GATE.

## E019 — Golden-generation pipeline produced a false-green step

Observed:
The first S5-CERT candidate `6a2b1ec9e1987a8a612dcfdb9ff8d032a4811828` showed the golden-generation step as successful, but `golden-run-1.txt` and `golden-run-2.txt` were empty and no `manifest.json` or PNGs existed. The following manifest-verification step correctly failed.

Root cause:
The workflow invoked `python scripts/s5_generate_goldens.py | tee ...` from `backend/` without making the backend package root available to the script import path, and the pipeline did not enable `pipefail`. The Python process could therefore fail before contacting Chromium while `tee` returned zero.

Correction:
The S5-CERT workflow now supplies `PYTHONPATH=${{ github.workspace }}/backend` and executes the golden generator under `set -o pipefail`. The Review Playwright evidence pipeline is also fail-closed with `pipefail`.

Status: REPAIRED / FIRST CANDIDATE SUPERSEDED.

## E020 — Pull-request merge ref is not the product candidate identity

Observed:
GitHub Actions checks out a synthetic merge ref for `pull_request` events, so `GITHUB_SHA`/`checkout_sha` can differ from `github.event.pull_request.head.sha`.

Risk:
Using the synthetic merge SHA as the certificate would bind evidence to a transient GitHub merge ref rather than the exact source branch head reviewed for S5.

Correction:
S5 receipts record both identities. Candidate freeze and product certification authority use the exact `pr_head_sha`; the synthetic merge SHA is retained only as CI execution context.

Status: DOCUMENTED / PROCESS GUARDRAIL.
