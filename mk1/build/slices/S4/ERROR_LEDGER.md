# MK1 S4 — VisualSpec V1 — Error / Near-Miss Ledger

Status: **FROZEN / CLOSED WITH S4 CERTIFICATE**

Purpose: preserve mistakes, ambiguous authority, false-green risks and corrective decisions discovered while building S4. This ledger is certification evidence; entries are never deleted merely because they were fixed.

## S4-E001 — S4 branch was created before the repository-hygiene entry descendant merged

Observed:

`mk1/s4-visualspec-v1` was initially created from pre-entry `main@2dd152e671667e1377907c53748aec83aaf4796b` while the S4-entry/hygiene documentation branch was still being prepared.

Risk:

Starting code immediately would create a split baseline: repository policy/status changes would be on a sibling branch instead of being ancestors of the S4 implementation.

Correction:

No S4 source change was allowed until the entry documentation PR merged and the S4 branch was aligned to exact entry `main@408f598bae5f200bbd90d9a06883cc740b69bcac`.

Prevention rule:

For each slice, finish and merge required entry reconciliation before the first product-code commit, or explicitly align the active slice branch to the certified entry SHA.

## S4-E002 — No `developer` branch exists

Observed:

Repository branch search returned no `developer` or `develop` branch.

Risk:

Inventing one would introduce a second merge authority without an ADR and make `main` vs `developer` precedence ambiguous.

Correction:

No integration branch was invented. `main` remains the single integration authority.

Prevention rule:

Do not invent branch topology. Repository workflow is an authority decision.

## S4-E003 — Profile visual architecture is richer than the persisted ProfileVersion visual contract

Observed:

Architecture describes typography roles, palette mapping, density, spacing/radius, icon language, image treatment and layout preferences. Certified `ProfileVersion.visual_system` persists only bounded free-form `traits`.

Risk:

S4 could silently fabricate a brand system, mutate S1 schema, or allow arbitrary styling/CSS authority through traits.

Correction:

S4 derives immutable/versioned `DesignProfileV1` through an allowlisted deterministic mapper from exact ProfileVersion plus controlled defaults. Unknown traits cannot inject arbitrary CSS, fonts, URLs, scripts, secrets or renderer directives.

Prevention rule:

When architecture is richer than a certified upstream contract, add a bounded derived policy layer unless an upstream migration is separately designed and certified.

## S4-E004 — Historical visual implementations are not MK1 S4 authority

Observed:

The repository contains pre-MK1 visual/rendering work.

Risk:

Direct reuse could bypass `VisualSpecV1`, mix render authority into S4, or import stale Commercial V1 assumptions.

Correction:

Historical work remains evidence/adapter material only. Every S4 output crosses the new typed VisualSpec boundary. Rendering remains S5.

Prevention rule:

Code reuse does not imply authority reuse.

## S4-E005 — Repository status/readmes were stale after S3 certification

Observed:

At S4 entry, canonical docs still described certified implementation as stopping at S2 and called S3 future work.

Risk:

Engineers/agents could make decisions from stale authority documents.

Correction:

S4-entry repository hygiene reconciled root README, `mk1/README.md` and `mk1/STATUS.md` before product implementation.

Prevention rule:

Every slice close includes documentation reconciliation; every next-slice entry verifies canonical status.

## S4-E006 — Stale open PRs could be mistaken for merge-ready authority

Observed:

PR #42 and historical draft PR #27 remained open at S4 entry.

Risk:

“Merge everything” cleanup could promote uncertified/stale code.

Correction:

Both were closed without merge and preserved as historical diagnostic/reconciliation evidence.

Prevention rule:

Classify each line as merge, archive or active before cleanup. Open does not mean authoritative.

## S4-E007 — Remote branch deletion is not equivalent to lineage cleanup

Observed:

The available GitHub action surface did not expose remote-ref deletion during repository cleanup.

Risk:

Force-moving old refs to `main` to simulate deletion would destroy historical tip identity.

Correction:

Historical refs were not rewritten. Cleanup state is documented; physical deletion remains a separate mechanical operation when proper delete-ref authority is available.

Prevention rule:

Never fake cleanup by mutating evidence.

## S4-E008 — S4 must not over-certify pixel quality

Observed:

Architecture splits VisualSpec intent (S4) from rendering/AssetStore (S5).

Risk:

Semantic golden fixtures could be mistaken for rendered visual-quality proof.

Correction:

S4 certifies schema, semantics, copy refs, deterministic mapping and lineage only. Pixel dimensions, clipping, typography rendering, asset bytes and visual QA remain downstream.

Prevention rule:

Every certificate includes explicit downstream non-claims.

## S4-E009 — VisualSpec persistence has a crash window before revision pointer binding

Observed:

The durable operation writes immutable `VisualSpecV1` before compare-and-set of `ContentRevision.visual_spec_ref`.

Risk:

A retry with random identity could create duplicate specs for one semantic attempt.

Correction:

The certified lineage uses deterministic same-attempt VisualSpec identity and immutable persistence. Retry can reopen the durable spec and finish pointer binding without replacing history.

Prevention rule:

When an immutable artifact precedes a mutable pointer, identity/retry semantics must treat the first write as durable intent.

## S4-E010 — Revision pointer may advance before GenerationRun mirror is updated

Observed:

A crash can occur after revision CAS and before `GenerationRun.visual_spec_ref` mirror update.

Risk:

Treating the run mirror as primary could fabricate another plan or reject valid durable lineage.

Correction:

`ContentRevision.visual_spec_ref` is the durable S4 binding. Retry reloads and validates that VisualSpec, then repairs the GenerationRun mirror to the same identity.

Prevention rule:

For duplicated pointers, define one authority and make mirrors recoverable from it.

## S4-E011 — S4 must not move GenerationRun to RENDERING

Observed:

The frozen state machine orders `VISUAL_PLANNING -> RENDERING`, which could tempt S4 to advance state when VisualSpec exists.

Risk:

That would claim render execution began even though S4 has no renderer or AssetStore authority.

Correction:

Successful S4 planning leaves `GenerationRun.state=VISUAL_PLANNING` and binds `visual_spec_ref`. S5 owns transition to `RENDERING` when execution actually begins.

Prevention rule:

State transitions represent real authority/side effects, not milestone optimism.

## S4-E012 — Deterministic planner path has no model-attempt evidence by design

Observed:

Certified S4 V1 derives DesignProfile and VisualSpec deterministically without a visual-model call.

Risk:

Certification could incorrectly fabricate `AgentAttemptEvidenceV1`, or a future model adapter could be added without S3-style evidence discipline.

Correction:

V1 records no fake provider attempts. Any future model-backed visual planner must add bounded structured-output repair and durable attempt evidence before becoming certified authority.

Prevention rule:

Do not fabricate telemetry for absent calls; do not add an external-model path without evidence and a new exact-SHA certification.

## Closure evidence

The ledger freezes only because the complete S4 chain closed:

```text
frozen candidate
75a0fc048bc172d4a394baf26d44739b3759b3a2
        ↓
6 / 6 candidate gates GREEN
        ↓
receipt head
1b056136d3a5a4aa5eec7588555531133dcb0680
        ↓
6 / 6 receipt-head gates GREEN
        ↓
PR #46 exact-head merge
6a0a653d615e7fa2d1d63bc41b6b265b19646202
        ↓
6 / 6 post-merge gates GREEN
```

Canonical certificate:

```text
mk1/test/evidence/S4/CERTIFICATION.md
```

No E001–E012 entry is removed from history because S4 is green. Future defects in S4 behavior discovered after this certificate must be opened as a new hardening slice/ledger rather than silently editing this frozen record.
