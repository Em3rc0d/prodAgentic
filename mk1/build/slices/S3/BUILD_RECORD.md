# MK1 S3 — Structured Four-Agent Text Cell — Build Record

Status: **IMPLEMENTATION + PRE-FREEZE DOCUMENTATION CLOSED — FREEZE NEXT**

## Slice ID

`S3 — Structured Four-Agent Text Cell`

## Objective

Transfer text-production authority from the legacy opaque-string pipeline into the frozen MK1 typed production boundary:

```text
ContentPlanV1
  -> ResearchPackV1
  -> ContentSpecV1
  -> EditorialReviewV1
  -> ContentRevisionV1
  -> VISUAL_PLANNING handoff
```

S3 intentionally stops before `VisualSpecV1`; visual planning remains S4 authority.

## Base authority

- certified `main`: `37292e17cfcbc50588aa248e1b14577637b3f68d`
- branch: `mk1/s3-structured-agent-cell`
- PR: `#43`
- S2 quality-hardening PR `#42` is deliberately not inherited; S3 started from the last certified main.

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

The legacy runtime already contained `ResearchAgent`, `ContentWriterAgent`, `EditorAgent`, `VisualAgent`, `ModelRouter` and `PipelineOrchestrator`. Those stage boundaries stream opaque prose and persist MK0-style records; they are not treated as satisfying MK1 contracts.

S3 reuses provider/model routing only behind typed S3 adapters. Agents never receive authoritative Mongo collection access.

## Implemented module boundary

```text
backend/domain/production/
  __init__.py
  models.py
  ports.py

backend/application/production/
  __init__.py
  service.py
  lifecycle.py

backend/infrastructure/agents/
  __init__.py
  structured_text.py

backend/infrastructure/mongo/
  production.py
  planning.py                 # S3 read + lifecycle transition support

backend/routes/
  production.py

backend/main.py               # canonical router mount
backend/db/mongo.py           # S3 indexes

backend/tests/
  test_s3_structured_agent_cell.py
  test_s3_structured_router_adapter.py
  test_s3_content_lifecycle.py
  test_s3_api_surface.py
  test_s3_failure_lineage.py
  test_mk1_s3_mongo.py

.github/workflows/
  s3-cert.yml
```

## Typed authority implemented

Registered/versioned Pydantic-compatible contracts include:

- `EvidenceRefV1`
- `ClaimV1`
- `ResearchPackV1`
- `ContentSpecV1`
- `EditorialReviewV1`
- `AgentAttemptEvidenceV1`
- `GenerationRunV1`
- `GenerationFailureV1`
- `ContentRevisionV1`

Format-specific text contracts cover:

- text;
- single image copy semantics;
- carousel slide semantics;
- infographic section semantics.

All authoritative S3 models reject unexpected fields.

## Agent production flow

```text
resolve ContentItem
  -> resolve exact persisted ContentPlan
  -> resolve frozen ProfileVersion
  -> resolve S3 service/model-router readiness
  -> atomic lifecycle claim: PLANNED -> PRODUCING
  -> GenerationRun.CREATED
  -> RESEARCHING
  -> ResearchPackV1
     -> NO_GO => fail closed
  -> WRITING
  -> ContentSpecV1
  -> EDITING
  -> EditorialReviewV1
     -> REVISE => bounded cycle
     -> REJECT => fail closed
     -> APPROVE_TEXT
  -> ContentRevisionV1(DRAFT)
  -> bind ContentItem.current_revision_id
  -> GenerationRun.VISUAL_PLANNING
  -> S4 authority
```

S3 does not fabricate `READY_FOR_REVIEW`; that requires later visual/QA authority.

## Core invariants

1. New S3 persisted business/evidence records are tenant-scoped.
2. Every authoritative agent stage ends in a versioned typed contract.
3. Research `NO_GO` is a domain stop, not a blind retry trigger.
4. Writer `claims_used` must resolve inside the exact `ResearchPackV1`.
5. Writer may not reference `forbidden` claims.
6. Editor may not introduce unknown/forbidden claim IDs.
7. Structured-output contract repair is bounded.
8. Writer/editor revision cycles are bounded.
9. Regeneration creates new run/revision provenance instead of overwriting history.
10. Provider/model/attempt/latency/token/cost/input-output digest lineage is persisted safely.
11. Attempt ordinals reflect real invocation order; separate repair/retry attempts cannot all claim ordinal `1`.
12. Failed/contract-repair attempts carried by adapter failures are persisted before terminal failure whenever a run exists.
13. A typed artifact that later fails domain/authority verification preserves its producing attempt and leaves the run explicitly `FAILED`.
14. Every post-creation failure path terminalizes `GenerationRun` with safe bounded failure metadata and completion time; successful S3 alone hands off at `VISUAL_PLANNING`.
15. Agents do not mutate domain state directly.
16. ContentItem lifecycle is application-owned, atomic and tenant-scoped.
17. Runtime/service readiness is resolved before `PLANNED -> PRODUCING` is claimed.
18. S3 feature exposure is fail-closed under `MK1_STRUCTURED_AGENT_CELL` and the master `MK1_ENABLED` gate.
19. S3 stops at `VISUAL_PLANNING`; S4 remains separate authority.
20. No publication/scheduling/external side-effect authority is introduced by S3.

## Feature flags

Existing frozen registry authority is reused:

```text
MK1_ENABLED
MK1_STRUCTURED_AGENT_CELL
```

`MK1_STRUCTURED_AGENT_CELL` defaults off and cannot activate while the master MK1 gate is off.

## Persistence

New tenant-scoped Mongo collections:

```text
generation_runs
agent_run_attempts
production_artifacts
content_revisions
```

Indexes enforce run/attempt/artifact/revision identity and support per-content lineage reads. `content_items` remains the ContentItem aggregate collection and receives atomic lifecycle/current-revision updates.

Failure lineage is not treated as secondary telemetry: safe failed/contract-repair attempts are durable audit evidence linked to the exact `GenerationRun`.

## API boundary

Canonical FastAPI app mounts:

```text
POST /api/content-items/{content_id}/produce-text
GET  /api/generation-runs/{run_id}
GET  /api/content-revisions/{revision_id}
```

The POST resolves the persisted ContentItem, exact persisted ContentPlan and frozen ProfileVersion server-side. The client does not supply arbitrary plan/profile authority. The canonical API-surface certification uses the FastAPI OpenAPI contract, avoiding dependence on internal route-class identity.

## Failure paths

- malformed structured output -> bounded contract repair, attempt evidence retained, then safe failure if exhausted;
- provider/routing failure -> classified safe failure with available attempt lineage persisted;
- typed-but-semantically-invalid artifact -> preserve producing attempt, fail closed, terminalize run;
- missing/wrong agent lineage -> fail closed;
- `ResearchPack.NO_GO` -> domain stop;
- unsupported/forbidden writer claim -> fail closed;
- editor introduced claim -> fail closed;
- editor `REJECT` -> run failure;
- editor revision budget exhausted -> run failure;
- persistence failure -> no fabricated success;
- concurrent/non-PLANNED production claim -> `409`/fail closed;
- unavailable S3 runtime dependency before lifecycle claim -> no `PRODUCING` mutation;
- S3 failure after lifecycle claim -> ContentItem `FAILED`;
- successful S3 text -> ContentItem remains `PRODUCING` and binds the DRAFT revision for S4.

## Error / near-miss record

See `mk1/build/slices/S3/ERROR_LEDGER.md`.

Notable historical candidates/runs are diagnostic only unless explicitly named by the final certification receipt. Important discoveries include:

- generic CI green at `3ebe0a66f3711c0f01301095b77163d908e59998` while the new production router was not mounted;
- first dedicated S3-CERT at `862f3760fe5be4c7580b4b0ed16b5b91f0e03d05` failed on a brittle API-route introspection assertion and also failed to preserve its own receipt artifact;
- subsequent pre-freeze audit found attempt ordinal, failed-attempt durability, semantic-failure terminalization and lifecycle-readiness ordering defects; all were repaired before freeze.

None of those superseded SHAs may be used as S3 certification evidence.

## Test/certification gates

Canonical gates remain mandatory:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
```

S3 adds:

```text
S3-CERT structured-agent-cell
```

The dedicated gate covers:

- canonical OpenAPI API surface;
- fail-closed feature flag behavior;
- strict contract validation and extra-field rejection;
- claim provenance enforcement;
- bounded structured repair/revision;
- accurate attempt ordinals;
- failed-attempt persistence;
- semantic-failure terminalization;
- ContentItem lifecycle transitions/readiness ordering;
- real Mongo lineage persistence and restart/reopen reads.

The S3 workflow records exact run identity before the first fallible gate so red runs remain auditable evidence rather than disappearing.

## Candidate freeze law

The certification candidate must be one exact SHA after implementation/documentation reconciliation. No source/test/workflow changes are allowed after freeze. If any such file changes, the candidate is invalidated and a new candidate SHA is required.

A later certification-receipt-only commit may reference the frozen product candidate; that receipt head must itself pass the required gates before merge.

The exact candidate SHA is intentionally not self-recorded in this pre-freeze file because a commit cannot truthfully contain its own final SHA. Freeze identity is recorded externally on PR #43 immediately after this reconciliation commit and then immutably in `mk1/test/evidence/S3/CERTIFICATION.md` after exact-candidate gates pass.

## Known limitations / explicit non-claims

- no S4 `VisualSpecV1` authority;
- no S5 renderer/AssetStore authority;
- no S6 QA/recovery authority;
- no S7 review/ApprovalBundleV2 authority;
- no S3 production UI is claimed/certified;
- no external research browsing capability is claimed merely because `ResearchAgent` exists; evidence quality is constrained by configured adapters/tools;
- no publication/scheduling authority is transferred in S3;
- PR #42 remains outside this lineage.

## Rollback

Disable `MK1_STRUCTURED_AGENT_CELL` or revert the S3 merge. Existing S0-S2 user behavior remains available because S3 is additive and fail-closed by default.

## Certification evidence

Pending exact candidate freeze and green exact-SHA runs. No S3 certification claim is valid until `mk1/test/evidence/S3/CERTIFICATION.md` records the exact frozen candidate and required run/job/artifact identities.
