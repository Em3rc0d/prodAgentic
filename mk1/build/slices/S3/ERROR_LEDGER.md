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

## S3-E009 — First dedicated S3-CERT API-surface assertion produced a false negative

Observed SHA: `862f3760fe5be4c7580b4b0ed16b5b91f0e03d05`

Observed run/job:
- workflow run: `34243390549`
- job: `102119043598`

What happened:
The canonical source at the tested head already imported and mounted `production_router`, but the first route-introspection test filtered `app.routes` through an `APIRoute` assumption and reported only root/health routes. The gate failed even though the source mount was present.

Why this mattered:
A certification gate must fail on a missing runtime contract, not on a brittle test representation of that contract.

Correction:
The API-surface test was changed to validate the canonical FastAPI OpenAPI path/method contract, while source mounting remains independently inspectable. The next S3-CERT passed the API-surface step.

Prevention rule:
For externally exposed HTTP authority, certify the framework's emitted API contract rather than relying solely on internal route-class identity.

## S3-E010 — Failed S3-CERT initially lost its own receipt artifact

Observed run/job:
- workflow run: `34243390549`
- job: `102119043598`

What happened:
`Record exact candidate evidence` was placed after blocking test steps. When the API-surface gate failed, the receipt directory was never created and the `always()` artifact upload failed with `No files were found`.

Risk:
A red candidate is diagnostic evidence too. Losing its run identity makes failure history harder to audit.

Correction:
The workflow now creates the run identity receipt immediately after checkout, before any gate can fail, and the artifact upload remains `if: always()`.

Prevention rule:
Certification workflows must persist immutable run identity before executing the first fallible gate.

## S3-E011 — Agent attempt ordinal was initially hard-coded to `1`

What happened:
The structured router adapter emitted separate attempt IDs for provider retries/contract repairs but `AgentAttemptEvidenceV1.attempt` was always written as `1`.

Risk:
Lineage had distinct identities but an inaccurate attempt sequence, weakening replay/audit semantics.

Correction:
Attempt evidence now records the real invocation ordinal across the structured adapter path, and tests assert distinct ordered lineage.

Prevention rule:
Lineage fields are evidence, not decoration. Every recorded ordinal/digest/status must reflect the actual execution path.

## S3-E012 — Failed structured attempts were carried by exceptions but could escape durable lineage

What happened:
`StructuredAgentAdapterError` preserved failed/contract-repair attempts in memory, but the application service originally handled the exception generically and could fail the `GenerationRun` without persisting those attempt records.

Risk:
The most important diagnostic attempts — malformed output, exhausted routing or contract repair — could disappear from Mongo while successful attempts remained auditable.

Correction:
The service now persists safe attempt evidence carried by structured-agent failures before terminalizing the run. `test_s3_failure_lineage.py` covers this fail-closed path.

Prevention rule:
Failure evidence must be at least as durable as success evidence.

## S3-E013 — Typed-but-semantically-invalid artifacts could leave a non-terminal run

What happened:
A provider could return JSON that validated against the Pydantic schema and therefore generated a `SUCCESS` attempt, while later domain verification rejected it (for example wrong authority/claim semantics). The earlier path could raise without reliably terminalizing the run.

Risk:
Mongo could contain a run apparently stuck in `RESEARCHING`, `WRITING`, or `EDITING` even though execution had already failed.

Correction:
Semantic contract failures preserve the attempt that produced the typed artifact and terminalize the `GenerationRun` as `FAILED` with bounded safe failure metadata and completion time. Regression coverage was added.

Prevention rule:
Every post-run-creation exit path must result in either the exact successful handoff state or an explicit terminal failure state.

## S3-E014 — Lifecycle claim could occur before runtime service readiness was known

What happened:
The API initially claimed `ContentItem: PLANNED -> PRODUCING` before constructing/validating the S3 service/model-router dependency.

Risk:
If the model router was unavailable before generation actually began, the ContentItem could be stranded in `PRODUCING` despite no valid agent-cell execution having started.

Correction:
The route now resolves ContentItem, persisted ContentPlan, frozen ProfileVersion and the S3 service/runtime dependency first; only then does it atomically claim `PLANNED -> PRODUCING` and execute the cell.

Prevention rule:
Do not mutate aggregate lifecycle until all non-mutating authority/readiness prerequisites for the transition have been satisfied.

## Ledger closure rule

This file may be marked `FROZEN` only after:
1. candidate SHA is frozen;
2. exact-candidate canonical CI + Docker + S3-CERT are green;
3. certification receipt records those run IDs;
4. receipt head itself is re-run through required gates;
5. merge and post-merge gates are green.
