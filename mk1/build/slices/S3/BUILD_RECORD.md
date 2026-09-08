# MK1 S3 — Structured Four-Agent Text Cell — Build Record

Status: **CERTIFIED / MERGED**

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

- certified S3 base `main`: `37292e17cfcbc50588aa248e1b14577637b3f68d`
- implementation branch: `mk1/s3-structured-agent-cell`
- implementation PR: `#43`
- S2 quality-hardening PR `#42` was deliberately not inherited; S3 started from the last certified main.

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

Format-specific text contracts cover text, single-image copy semantics, carousel slide semantics and infographic section semantics. All authoritative S3 models reject unexpected fields.

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

S3 does not fabricate `READY_FOR_REVIEW`; later visual/QA authority is required.

## Core invariants

1. New S3 persisted business/evidence records are tenant-scoped.
2. Every authoritative agent stage ends in a versioned typed contract.
3. Research `NO_GO` is a domain stop, not a blind retry trigger.
4. Writer `claims_used` must resolve inside the exact `ResearchPackV1`.
5. Writer may not reference forbidden claims.
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

Failure lineage is not secondary telemetry: safe failed/contract-repair attempts are durable audit evidence linked to the exact `GenerationRun`.

## API boundary

Canonical FastAPI app mounts:

```text
POST /api/content-items/{content_id}/produce-text
GET  /api/generation-runs/{run_id}
GET  /api/content-revisions/{revision_id}
```

The POST resolves the persisted ContentItem, exact persisted ContentPlan and frozen ProfileVersion server-side. The client does not supply arbitrary plan/profile authority. API-surface certification validates the emitted FastAPI OpenAPI contract.

## Failure paths

- malformed structured output -> bounded contract repair, attempt evidence retained, then safe failure if exhausted;
- provider/routing failure -> classified safe failure with available attempt lineage persisted;
- typed-but-semantically-invalid artifact -> preserve producing attempt, fail closed, terminalize run;
- missing/wrong agent lineage -> fail closed;
- `ResearchPack.NO_GO` -> domain stop;
- unsupported/forbidden writer claim -> fail closed;
- editor-introduced claim -> fail closed;
- editor `REJECT` -> run failure;
- editor revision budget exhausted -> run failure;
- persistence failure -> no fabricated success;
- concurrent/non-PLANNED production claim -> `409`/fail closed;
- unavailable S3 runtime dependency before lifecycle claim -> no `PRODUCING` mutation;
- S3 failure after lifecycle claim -> ContentItem `FAILED`;
- successful S3 text -> ContentItem remains `PRODUCING` and binds the DRAFT revision for S4.

## Error / near-miss record

The complete preserved history is in `mk1/build/slices/S3/ERROR_LEDGER.md`. Superseded candidates are diagnostic only and are never mixed into certification evidence.

Key historical findings included:

- `3ebe0a66f3711c0f01301095b77163d908e59998`: generic CI green while the production router was not mounted;
- `862f3760fe5be4c7580b4b0ed16b5b91f0e03d05`: first S3-CERT false-negative API assertion and missing red-run artifact;
- `bbe4a1f555d626d6e9a1a11420d8bf8d5a8823dc`: S3-CERT green before the later pre-freeze lineage/lifecycle audit exposed additional defects;
- `dd3c88425c4734d5e126d98d12941189cf103e88`: implementation/test fixes present before final documentation reconciliation.

## Certification lineage

### Frozen implementation candidate

```text
9d5db5bb375af0522c4d14c946abb70805147d64
```

Exact-candidate consensus: **5/5 GREEN**.

Canonical CI run `34245422425`:

```text
frontend-test       102126042931  SUCCESS
backend-test        102126043234  SUCCESS
UI-01-CERT browser  102126970775  SUCCESS
```

UI artifact:

```text
10063952055
sha256:84a80445b004423500452ddf36e6afca03f09a4c4db5e3f32d16eda424d5bb77
```

Docker run `34245422470`:

```text
DOCKER-COMPOSE-LOCAL smoke  102126352360  SUCCESS
artifact 10063863411
sha256:c88ba2033879874b725dfb696d2a78c2ee07e2893fb915a2276a36c4ab6aaad4
```

S3-CERT run `34245422434`:

```text
S3-CERT structured-agent-cell  102126042190  SUCCESS
artifact 10063858139
sha256:f418236bf9b992efa56e51e1b1c95cdd1ffd67fc7541e2bf89ecb4df552cf92e
```

### Receipt-only head

```text
53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e
```

Candidate -> receipt-head diff: exactly one added file, `mk1/test/evidence/S3/CERTIFICATION.md`; no source/test/workflow/contract changes.

Receipt-head consensus: **5/5 GREEN**.

Canonical CI run `34246081563`:

```text
frontend-test       102128292395  SUCCESS
backend-test        102128292618  SUCCESS
UI-01-CERT browser  102129096094  SUCCESS
```

UI artifact:

```text
10064189303
sha256:e20d19bc4ea04bf546900e9d9b7e0e87f40df122f39d1cf9383e0ceda7164455
```

Docker run `34246081967`:

```text
DOCKER-COMPOSE-LOCAL smoke  102128294508  SUCCESS
artifact 10064097405
sha256:836b7594cafa6b71e5e04bd5a5df332ff6428dc4260e15aab15f39344300e87e
```

S3-CERT run `34246081710`:

```text
S3-CERT structured-agent-cell  102128293097  SUCCESS
artifact 10064054295
sha256:48ad9307188a1921f3dd3f907ed19ff8e39d18f76f70006727b3d6c7c1fc585c
```

### Exact-head protected merge

PR #43 was merged using expected head `53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e`.

S3 merge/product certificate boundary:

```text
a10dfec7f5851ae3f8c850fcc934009951f7d422
```

Merge parents:

```text
37292e17cfcbc50588aa248e1b14577637b3f68d
53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e
```

### Post-merge verification on exact merge SHA

Post-merge consensus: **5/5 GREEN**.

Canonical CI run `34246650579`:

```text
frontend-test       102130244987  SUCCESS
backend-test        102130245276  SUCCESS
UI-01-CERT browser  102131255966  SUCCESS
```

UI artifact:

```text
10064443584
sha256:89f1641e25f024ea6f105bc6554965a993fffd495735fc0a0ebe857332782d3a
```

Docker run `34246650596`:

```text
DOCKER-COMPOSE-LOCAL smoke  102130244212  SUCCESS
artifact 10064320322
sha256:365179a226b5d751e6a9c93791eb87d5e2e5fd4dcb5bdaa10ed24a36ebb6e907
```

S3-CERT run `34246650642`:

```text
S3-CERT structured-agent-cell  102130243417  SUCCESS
artifact 10064282259
sha256:afa6e47483a582dde62b9ef5e6cde34f251fea1ee2c5a4e8230606ed0f3286f7
```

## Known limitations / explicit non-claims

- no S4 `VisualSpecV1` authority;
- no S5 renderer/AssetStore authority;
- no S6 QA/recovery authority;
- no S7 review/ApprovalBundleV2 authority;
- no S3-specific production UI is claimed/certified;
- no unrestricted external research browsing capability is claimed;
- no publication/scheduling authority is transferred in S3;
- PR #42 remains outside this lineage.

## Rollback

Disable `MK1_STRUCTURED_AGENT_CELL` or revert the S3 merge. Existing S0-S2 user behavior remains available because S3 is additive and fail-closed by default.

## Final decision

```text
FROZEN CANDIDATE        9d5db5bb375af0522c4d14c946abb70805147d64
RECEIPT HEAD            53fc5ae804bcbcd4e85ae0f0c02f8fb5b3000d2e
S3 MERGE SHA            a10dfec7f5851ae3f8c850fcc934009951f7d422
CANDIDATE GATES         5/5 GREEN
RECEIPT-HEAD GATES      5/5 GREEN
POST-MERGE GATES        5/5 GREEN
S3                      CERTIFIED / MERGED
```
