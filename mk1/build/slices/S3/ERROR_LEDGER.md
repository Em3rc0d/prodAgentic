# MK1 S3 — Error / Near-Miss Ledger

Status: **FROZEN — S3 CERTIFIED / MERGED**

Purpose: preserve mistakes, near-misses, false-positive risks and corrective actions discovered while building S3. This ledger is part of certification evidence; it is not a blame record. Nothing below is erased because a later candidate passed.

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
The existing canonical browser suite was aimed at S0-S2 UI behavior. S3 had no certified frontend UI, and no test asserted that the new route was mounted on `main.app`.

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
The build record was reconciled before candidate freeze and is closed after merge with exact candidate, receipt, merge and post-merge evidence.

Prevention rule:
Every candidate freeze includes a documentation reconciliation pass before certification, followed by a post-merge documentation closure.

## S3-E003 — Dedicated S3 feature flag already existed

What happened:
At slice opening, a dedicated S3 flag was listed as a pending requirement. Inspection showed `MK1_STRUCTURED_AGENT_CELL` was already present in the frozen feature-flag registry and defaulted fail-closed.

Risk:
Adding a second/renamed flag would have created competing configuration authority.

Correction:
Reused the existing `FeatureFlag.MK1_STRUCTURED_AGENT_CELL`; tests prove default-off behavior and master-gate dominance.

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
Agent lineage and aggregate lifecycle must be reconciled before candidate freeze.

## S3-E005 — Generic browser certification is not an S3 semantic evaluation

What happened:
`UI-01-CERT browser` can pass while S3 is completely feature-gated off because S3 does not own a production UI in this slice.

Risk:
Treating UI-01-CERT as an S3 agent-quality certificate would over-certify.

Correction:
Added `.github/workflows/s3-cert.yml`, explicitly covering API mount/feature gates, contracts, structured-output repair, lifecycle and real Mongo lineage/restart.

Prevention rule:
Canonical CI remains necessary, never sufficient, when a slice introduces new non-UI authority.

## S3-E006 — S2 quality-hardening PR #42 intentionally remained outside S3 lineage

What happened:
PR #42 was open and uncertified. Starting S3 from it would have contaminated S3 evidence with an uncertified S2 candidate.

Correction:
S3 branch was created from certified `main@37292e17cfcbc50588aa248e1b14577637b3f68d`.

Consequence:
S3 certification does not certify or silently absorb the S2Q topic-authority repair.

Prevention rule:
A downstream slice may only inherit a prior candidate when that candidate is itself certified/merged or explicitly promoted through a documented reconciliation gate.

## S3-E007 — Legacy agent implementation is not MK1 contract authority

Observed condition:
The repository already had `ResearchAgent`, `ContentWriterAgent`, `EditorAgent`, `VisualAgent`, `ModelRouter`, and `PipelineOrchestrator`, but their stage boundaries were opaque prose streams/MK0 persistence.

Risk:
Calling those existing classes the S3 engine would silently bypass the frozen typed contracts.

Correction:
Reused provider/model routing only behind new typed S3 adapters and Pydantic contracts. Agents do not receive Mongo authority.

Prevention rule:
Historical capability can be adapted; it cannot be relabeled as satisfying a new authority contract without evidence.

## S3-E008 — Visual authority must not leak into S3

Observed temptation:
The legacy pipeline already included a VisualAgent, making it easy to accidentally claim end-to-end content production in S3.

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
The canonical source at the tested head already imported and mounted `production_router`, but the first route-introspection test filtered `app.routes` through an `APIRoute` assumption and reported only root/health routes.

Why this mattered:
A certification gate must fail on a missing runtime contract, not on a brittle representation of that contract.

Correction:
The API-surface test was changed to validate the canonical FastAPI OpenAPI path/method contract. The next S3-CERT passed the API-surface step.

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
Attempt evidence now records the real invocation ordinal, and tests assert distinct ordered lineage.

Prevention rule:
Lineage fields are evidence, not decoration.

## S3-E012 — Failed structured attempts were carried by exceptions but could escape durable lineage

What happened:
`StructuredAgentAdapterError` preserved failed/contract-repair attempts in memory, but the application service originally handled the exception generically and could fail the `GenerationRun` without persisting those attempt records.

Risk:
Malformed output, exhausted routing or contract-repair attempts could disappear from Mongo while successful attempts remained auditable.

Correction:
The service persists safe attempt evidence carried by structured-agent failures before terminalizing the run. `test_s3_failure_lineage.py` covers this path.

Prevention rule:
Failure evidence must be at least as durable as success evidence.

## S3-E013 — Typed-but-semantically-invalid artifacts could leave a non-terminal run

What happened:
A provider could return JSON that validated against the Pydantic schema and generated a `SUCCESS` attempt, while later domain verification rejected it. The earlier path could raise without reliably terminalizing the run.

Risk:
Mongo could contain a run stuck in `RESEARCHING`, `WRITING`, or `EDITING` even though execution had failed.

Correction:
Semantic contract failures preserve the attempt that produced the typed artifact and terminalize the `GenerationRun` as `FAILED` with bounded safe failure metadata and completion time.

Prevention rule:
Every post-run-creation exit path must result in either the exact successful handoff state or an explicit terminal failure state.

## S3-E014 — Lifecycle claim could occur before runtime service readiness was known

What happened:
The API initially claimed `ContentItem: PLANNED -> PRODUCING` before constructing/validating the S3 service/model-router dependency.

Risk:
If the model router was unavailable, the ContentItem could be stranded in `PRODUCING` despite no valid agent-cell execution having started.

Correction:
The route now resolves ContentItem, persisted ContentPlan, frozen ProfileVersion and S3 service/runtime dependency first; only then does it atomically claim `PLANNED -> PRODUCING`.

Prevention rule:
Do not mutate aggregate lifecycle until all non-mutating authority/readiness prerequisites for the transition have been satisfied.

## Closure evidence

The ledger closure rule was satisfied without deleting or rewriting the diagnostic history.

Frozen implementation candidate:

```text
9d5db5bb375af0522c4d14c946abb70805147d64
```

Exact-candidate gates: **5/5 GREEN**.

Receipt-only head:

```text
53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e
```

Candidate -> receipt-head diff: only `mk1/test/evidence/S3/CERTIFICATION.md` added. Receipt-head gates: **5/5 GREEN**.

Exact-head protected merge:

```text
PR #43
expected head: 53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e
merge SHA:     a10dfec7f5851ae3f8c850fcc934009951f7d422
```

Post-merge exact-SHA evidence:

```text
canonical CI run     34246650579
  frontend-test      102130244987  SUCCESS
  backend-test       102130245276  SUCCESS
  UI-01-CERT browser 102131255966  SUCCESS

Docker run           34246650596
  job                102130244212  SUCCESS

S3-CERT run          34246650642
  job                102130243417  SUCCESS
```

Post-merge artifacts:

```text
UI evidence
  id      10064443584
  sha256  89f1641e25f024ea6f105bc6554965a993fffd495735fc0a0ebe857332782d3a

Docker evidence
  id      10064320322
  sha256  365179a226b5d751e6a9c93791eb87d5e2e5fd4dcb5bdaa10ed24a36ebb6e907

S3 evidence
  id      10064282259
  sha256  afa6e47483a582dde62b9ef5e6cde34f251fea1ee2c5a4e8230606ed0f3286f7
```

## Ledger closure decision

The original closure rule required:
1. candidate SHA frozen — **PASS**;
2. exact-candidate canonical CI + Docker + S3-CERT green — **PASS**;
3. certification receipt with exact run IDs — **PASS**;
4. receipt head re-run through required gates — **PASS**;
5. merge and post-merge gates green — **PASS**.

Therefore this ledger is now **FROZEN**. Any future S3 issue is a new post-certification incident/erratum and must be appended through a new documented change; historical entries E001–E014 remain immutable evidence of the engineering path to certification.
