# MK1 S3 — Structured Four-Agent Text Cell — Build Record

Status: **IN PROGRESS — NOT CERTIFIED**

## Slice ID

`S3 — Structured Four-Agent Text Cell`

## Objective

Transfer text-production authority from the legacy opaque-string pipeline into the frozen MK1 typed production boundary:

```text
ContentPlanV1
  -> ResearchPackV1
  -> ContentSpecV1
  -> EditorialReviewV1
  -> ContentRevision
```

S3 intentionally stops before `VisualSpecV1`; visual planning remains S4 authority.

## Base authority

- certified `main`: `37292e17cfcbc50588aa248e1b14577637b3f68d`
- branch: `mk1/s3-structured-agent-cell`
- S2 quality-hardening PR #42 is deliberately **not** a dependency of this branch; S3 starts from the last certified main and must not silently inherit an uncertified S2 candidate.

## Accepted design dependencies

- `mk1/arch/CONTRACTS.md`
- `mk1/arch/AGENT_ARCHITECTURE.md`
- `mk1/arch/DOMAIN_MODEL.md`
- `mk1/arch/STATE_MACHINES.md`
- `mk1/arch/INVARIANTS.md`
- `mk1/arch/GOVERNANCE_QA.md`
- `mk1/build/CODE_RULES.md`
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md`
- `mk1/test/TEST_STRATEGY.md`

## Existing runtime inspected

Legacy generation already contains `ResearchAgent`, `ContentWriterAgent`, `EditorAgent`, `VisualAgent`, `ModelRouter` and `PipelineOrchestrator`. That path streams opaque strings and persists MK0-style `content_runs`/`posts`; it is **not** treated as satisfying the MK1 typed contracts.

S3 will adapt/reuse provider routing capabilities only behind new typed ports. Agents never write MK1 authoritative state directly.

## New module boundary

```text
backend/domain/production/
  models.py
  ports.py

backend/application/production/
  service.py
```

Later commits in the same slice may add model-backed adapters and an API boundary, but the domain/application authority is defined first.

## Core invariants for this slice

1. Every new persisted business record carries `tenant_id`.
2. Every authoritative agent output is a registered/versioned typed contract.
3. Research `NO_GO` stops production; it is not blindly retried as a transport failure.
4. Writer `claims_used` must reference claims in the exact ResearchPack and may not reference forbidden claims.
5. Editor revisions may not introduce claim IDs outside the exact ResearchPack.
6. `REVISE` is bounded; no infinite writer/editor loop.
7. Regeneration creates a new `GenerationRun`; prior provenance is immutable.
8. S3 produces a DRAFT text revision and leaves visual planning to S4.
9. Provider/model/attempt/latency/token-cost metadata and input/output digests are persisted as safe lineage evidence.
10. Secrets and raw provider credentials never enter typed artifacts or lineage metadata.

## Feature flags

S3 runtime exposure will be guarded by a dedicated MK1 flag before any existing user path is switched. No MK0/MK1 publication authority changes occur in this slice.

## Failure paths

- malformed structured output -> adapter-level bounded contract repair;
- `ResearchPack.NO_GO` -> domain stop / attention state;
- unsupported or unknown claim IDs -> fail closed;
- editor `REJECT` -> run failure / attention state;
- editor revision budget exhausted -> run failure / attention state;
- persistence failure -> do not fabricate success;
- provider/routing failure -> classified failure with safe evidence.

## Tests required

- valid/invalid contract fixtures;
- extra-field rejection;
- unsupported writer claim rejection;
- editor-introduced claim rejection;
- `NO_GO` fail-closed behavior;
- bounded revision loop;
- generation lineage preserves provider/model/digests;
- regeneration creates a distinct run/revision;
- tenant authority mismatch rejection;
- prior backend suite remains green.

## Certification evidence

Not yet issued. S3 cannot be marked certified until one exact candidate SHA passes the canonical backend/frontend/browser CI gates plus any S3-specific contract/evaluation gates introduced by this branch.

## Known limitations at slice opening

- no S4 `VisualSpecV1` authority;
- no S5 renderer authority;
- no S6 QA authority;
- no S7 approval authority;
- no S3 production UI is certified yet;
- PR #42 remains outside this branch and is not silently merged/rebased into S3.

## Rollback

Disable the S3 feature flag / revert the S3 branch merge. Existing certified S0-S2 behavior remains authoritative because this slice does not replace it until separately certified.
