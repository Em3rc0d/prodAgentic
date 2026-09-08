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
