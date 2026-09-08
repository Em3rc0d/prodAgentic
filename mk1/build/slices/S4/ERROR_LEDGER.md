# MK1 S4 — VisualSpec V1 — Error / Near-Miss Ledger

Status: **ACTIVE FROM BUILD ENTRY**

Purpose: preserve mistakes, ambiguous authority, false-green risks and corrective decisions discovered while building S4. This ledger is certification evidence; entries are never deleted merely because they were fixed.

## S4-E001 — S4 branch was created before the repository-hygiene entry descendant merged

Observed:

`mk1/s4-visualspec-v1` was initially created from pre-entry `main@2dd152e671667e1377907c53748aec83aaf4796b` while the S4-entry/hygiene documentation branch was still being prepared.

Risk:

Starting code immediately would create a split baseline: repository policy/status changes would be on a sibling branch instead of being ancestors of the S4 implementation.

Correction:

No S4 source change is allowed on that branch until the entry documentation PR is merged and the S4 branch ref is fast-forwarded/aligned to the resulting exact `main` SHA.

Prevention rule:

For each slice, finish and merge any required entry reconciliation before the first product-code commit, or explicitly merge/rebase the active slice branch onto the certified entry SHA before implementation.

## S4-E002 — No `developer` branch exists

Observed:

Repository branch search returned no `developer` or `develop` branch.

Risk:

Creating an integration branch just because cleanup requested “developer if there is one” would introduce a new source of merge authority without a design decision, and could make `main` vs `developer` precedence ambiguous.

Correction:

Do not create one. `main` remains the single integration authority until an explicit workflow ADR/policy says otherwise.

Prevention rule:

Do not invent branch topology. Repository workflow is an authority decision and must be documented before use.

## S4-E003 — Profile visual architecture is richer than the current persisted ProfileVersion visual contract

Observed:

Architecture describes DesignProfile dimensions such as typography roles, palette mapping, density, spacing/radius, icon language, image treatment and layout preferences. Current `ProfileVersion.visual_system` persists only a bounded tuple of free-form `traits`.

Risk:

S4 could silently fabricate a full brand system, mutate S1 schema, or allow arbitrary styling/CSS authority through free-form strings.

Correction decision:

S4 will derive an immutable, versioned `DesignProfileV1` through an allowlisted deterministic mapper from the frozen ProfileVersion snapshot plus controlled defaults/presets. Unknown traits may not inject arbitrary CSS, fonts, URLs, scripts, secrets or renderer directives.

Prevention rule:

When architecture is richer than a certified upstream persisted contract, add a bounded derived policy layer unless a deliberate upstream schema migration is separately designed/certified.

## S4-E004 — Historical visual implementations are tempting but are not MK1 S4 authority

Observed:

The repository contains extensive pre-MK1 visual/rendering work, including historical deterministic rendering and generative visual paths on archived reconciliation/feature branches.

Risk:

Reusing those objects directly could bypass `VisualSpecV1`, mix render authority into S4, or import stale Commercial V1 assumptions into the certified MK1 line.

Correction:

Historical work may be mined for adapter techniques only. Every accepted S4 output must cross the new typed VisualSpec boundary and satisfy current MK1 contracts. Rendering stays in S5.

Prevention rule:

Code reuse does not imply authority reuse. Reused implementation must sit behind the current frozen contract.

## S4-E005 — Repository status/readmes were stale after S3 certification

Observed:

At S4 entry, `README.md`, `mk1/README.md` and `mk1/STATUS.md` still described the certified implementation as stopping at S2 and called S3 future work, even though S3 had already been certified/merged and its documentation descendant closed.

Risk:

A new engineer/agent following the documented reading order could make wrong architecture/build decisions from stale canonical status.

Correction:

S4-entry repository hygiene updates all three canonical entry documents before product implementation begins.

Prevention rule:

Every slice close must include a documentation reconciliation gate, and every next-slice entry must verify canonical status/readmes before source changes.

## S4-E006 — Stale open PRs could be mistaken for merge-ready authority

Observed:

PR #42 (`mk1/s2-quality-hardening`) and historical draft PR #27 (`reconcile/commercial-v1-main-first`) remained open at S4 entry.

Risk:

“Merge everything” cleanup could accidentally promote uncertified/stale code into current main or imply those lines were current work.

Correction:

Both PRs were explicitly commented and closed without merge. Their history is preserved, with reasons documented in `mk1/build/REPOSITORY_HYGIENE.md`.

Prevention rule:

Repository cleanup classifies each line as merge, archive or active before any merge/deletion operation. Open does not mean authoritative.

## S4-E007 — Remote branch deletion is not equivalent to lineage cleanup

Observed:

The connected GitHub action surface available in this execution supports branch create/search/update but not remote-ref deletion.

Risk:

Force-moving old branch refs to `main` to simulate deletion would destroy useful historical branch-tip identity and weaken auditability.

Correction:

Do not rewrite historical refs. Merge/archive PRs now; maintain a verified deletion list for the final mechanical GitHub-admin cleanup when a delete-ref capability/UI is available.

Prevention rule:

Never fake a cleanup operation by mutating evidence. Tool limitations must remain explicit.

## S4-E008 — S4 must not over-certify pixel quality

Observed:

The architecture explicitly splits VisualSpec intent (S4) from Chromium rendering/AssetStore (S5).

Risk:

Golden semantic/layout snapshots might look convincing enough to claim “visual quality” even though no pixels or final assets have been rendered.

Correction:

S4 golden tests certify schema, semantics, copy references, deterministic mapping and lineage only. Pixel dimensions, clipping, typography rendering, asset bytes and visual QA remain S5/S6 claims.

Prevention rule:

Every certificate states explicit non-claims for downstream slices.

## Ledger discipline

Append new entries whenever:

- an implementation assumption proves wrong;
- a green generic gate misses an S4-specific authority boundary;
- a test itself produces a false positive/negative;
- a model/repair path loses evidence;
- a visual spec can introduce unsupported critical copy or factual specificity;
- a persistence/restart path leaves ambiguous state;
- a scope decision would leak renderer/S5 authority backward.

This file freezes only after exact-candidate gates, receipt-head revalidation, exact-head merge and post-merge consensus are green.
