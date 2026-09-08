# MK1 S3 — Error / Near-Miss Ledger

Status: **ACTIVE THROUGH CANDIDATE FREEZE**

Purpose: preserve mistakes, near-misses, false-positive risks and corrective actions discovered while building S3. This ledger is part of certification evidence; it is not a blame record.

## S3-E001 — Green standard CI did not prove the new API was reachable

Observed candidate: `3ebe0a66f3711c0f01301095b77163d908e59998`

What happened:
- `routes/production.py` existed;
- S3 domain/application/adapter/Mongo tests existed;
- canonical backend/frontend/browser/Docker checks passed;
- but `backend/main.py` had not mounted `production_router`.

Why this mattered:
A green suite could have been misread as a product-level S3 certificate even though no canonical FastAPI route exposed the new boundary.

Root cause:
The existing canonical browser suite is aimed at S0-S2 UI behavior. S3 has no certified frontend UI yet, and no test asserted that the new route was mounted on `main.app`.

Correction:
- mounted `production_router` in `backend/main.py`;
- added `backend/tests/test_s3_api_surface.py`;
- added a dedicated `S3-CERT structured-agent-cell` workflow.

Prevention rule:
A new slice cannot use generic CI green as proof of runtime exposure. It must contain at least one slice-specific gate that checks its actual authority boundary.

## S3-E002 — Build record became stale while implementation advanced

What happened:
The opening `BUILD_RECORD.md` correctly said model-backed adapters/API/persistence would be added later, but those components were subsequently implemented while the opening wording remained unchanged.

Risk:
Documentation could lag code and misstate the actual certification surface.

Correction:
The build record is rewritten before candidate freeze and the candidate/receipt documents reference exact SHAs rather than narrative status alone.

Prevention rule:
Every candidate freeze includes a documentation reconciliation pass before certification.

## S3-E003 — Dedicated S3 feature flag already existed

What happened:
At slice opening, a dedicated S3 flag was listed as a pending requirement. Inspection showed `MK1_STRUCTURED_AGENT_CELL` was already present in the frozen feature-flag registry and defaulted fail-closed.

Risk:
Adding a second/renamed flag would have created competing configuration authority.

Correction:
Reuse the existing `FeatureFlag.MK1_STRUCTURED_AGENT_CELL`; add tests proving default-off behavior and master-gate dominance.

Prevention rule:
Before adding infrastructure/configuration primitives, inspect frozen registries and existing authority first.

## S3-E004 — ContentItem lifecycle was initially left at S2-only `PLANNED`

What happened:
The first S3 implementation created durable GenerationRuns and ContentRevisions but did not yet bind the ContentItem lifecycle to the frozen state machine.

Why this mattered:
A successful production run could exist while the source ContentItem still claimed `PLANNED`, creating contradictory domain state.

Correction:
- expanded `ContentEditorialState` to the frozen lifecycle values;
- added `ContentProductionLifecycle` in the application layer;
- added atomic tenant-scoped ContentItem transition support in `MongoPlanningRepository`;
- S3 begin: `PLANNED -> PRODUCING`;
- successful text handoff binds `current_revision_id` while remaining `PRODUCING` for S4;
- failed S3 attempt: `PRODUCING -> FAILED`;
- added lifecycle tests.

Prevention rule:
Agent lineage and aggregate lifecycle must be reconciled before candidate freeze; one cannot be certified while the other tells a conflicting story.

## S3-E005 — Generic browser certification is not an S3 semantic evaluation

What happened:
`UI-01-CERT browser` can pass while S3 is completely feature-gated off because S3 does not yet own a production UI.

Risk:
Treating UI-01-CERT as an S3 agent-quality certificate would over-certify.

Correction:
Added `.github/workflows/s3-cert.yml`, which explicitly runs:
- API mount/feature-gate checks;
- contract/orchestration tests;
- malformed structured-output repair tests;
- lifecycle checks;
- real Mongo lineage/restart tests.

Prevention rule:
Canonical CI remains necessary, never sufficient, when a slice introduces new non-UI authority.

## S3-E006 — S2 quality-hardening PR #42 intentionally remains outside S3 lineage

What happened:
PR #42 is open and not certified. Starting S3 from it would contaminate S3 evidence with an uncertified S2 candidate.

Correction:
S3 branch was created from certified `main@37292e17cfcbc50588aa248e1b14577637b3f68d`.

Consequence:
S3 certification does not certify or silently absorb the S2Q topic-authority repair. That work remains a separate historical/open line unless explicitly reconciled later.

Prevention rule:
A downstream slice may only inherit a prior candidate when that candidate is itself certified/merged or explicitly promoted through a documented reconciliation gate.

## S3-E007 — Legacy agent implementation is not MK1 contract authority

Observed condition:
The repository already had `ResearchAgent`, `ContentWriterAgent`, `EditorAgent`, `VisualAgent`, `ModelRouter`, and `PipelineOrchestrator`, but their stage boundaries are opaque prose streams/MK0 persistence.

Risk:
Calling those existing classes 'the S3 engine' would silently bypass the frozen typed contracts.

Correction:
Reuse provider/model routing only behind new typed S3 adapters and new Pydantic contracts. Agents do not receive Mongo authority.

Prevention rule:
Historical capability can be adapted; it cannot be relabeled as satisfying a new authority contract without evidence.

## S3-E008 — Visual authority must not leak into S3

Observed temptation:
The legacy pipeline already includes a VisualAgent, which could make it easy to claim end-to-end content production in S3.

Correction:
S3 stops at `GenerationRun.state = VISUAL_PLANNING` with a `DRAFT` ContentRevision. `VisualSpecV1` remains S4 authority.

Prevention rule:
Do not broaden a slice to make a certificate sound more complete. Preserve frozen slice boundaries.

## Ledger closure rule

This file may be marked `FROZEN` only after:
1. candidate SHA is frozen;
2. exact-candidate canonical CI + Docker + S3-CERT are green;
3. certification receipt records those run IDs;
4. receipt head itself is re-run through required gates;
5. merge and post-merge gates are green.
