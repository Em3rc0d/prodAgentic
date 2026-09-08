# MK1 S3 — Structured Agent Cell — Candidate Certification Receipt

Status: **EXACT CANDIDATE VERIFIED — RECEIPT HEAD REVALIDATION PENDING**

This receipt certifies the exact frozen S3 implementation candidate below. It is not yet the final post-merge certificate.

## Frozen candidate

```text
9d5db5bb375af0522c4d14c946abb70805147d64
```

Authority line:

```text
base main: 37292e17cfcbc50588aa248e1b14577637b3f68d
branch:    mk1/s3-structured-agent-cell
PR:        #43
```

The freeze was declared on PR #43 before certification. After freeze, no source, test, workflow, architecture or contract changes are permitted. A later receipt/documentation-only head is allowed and must be revalidated independently.

## Exact-candidate gate consensus

All required gates below ran on the exact SHA `9d5db5bb375af0522c4d14c946abb70805147d64`.

### Canonical CI

Workflow run:

```text
34245422425
```

Jobs:

```text
frontend-test       102126042931   SUCCESS
backend-test        102126043234   SUCCESS
UI-01-CERT browser  102126970775   SUCCESS
```

UI certification artifact:

```text
artifact id:   10063952055
name:          ui-01-cert-evidence
sha256:        84a80445b004423500452ddf36e6afca03f09a4c4db5e3f32d16eda424d5bb77
```

### Docker Compose local-stack regression

Workflow run:

```text
34245422470
```

Job:

```text
DOCKER-COMPOSE-LOCAL smoke  102126352360  SUCCESS
```

Evidence artifact:

```text
artifact id:   10063863411
name:          docker-compose-local-evidence
sha256:        c88ba2033879874b725dfb696d2a78c2ee07e2893fb915a2276a36c4ab6aaad4
```

### S3-specific semantic certification

Workflow run:

```text
34245422434
```

Job:

```text
S3-CERT structured-agent-cell  102126042190  SUCCESS
```

Evidence artifact:

```text
artifact id:   10063858139
name:          s3-structured-agent-cell-evidence
sha256:        f418236bf9b992efa56e51e1b1c95cdd1ffd67fc7541e2bf89ecb4df552cf92e
```

The S3-CERT job completed successfully through all of its certification steps:

- exact run identity recorded before fallible gates;
- S3 module compile gate;
- canonical OpenAPI/API mount verification;
- fail-closed feature-flag verification;
- typed contract/orchestration checks;
- claim provenance checks;
- bounded structured-repair and editor-revision checks;
- ContentItem lifecycle checks;
- failed-attempt lineage checks;
- semantic-failure terminalization checks;
- real Mongo lineage persistence and restart/reopen checks;
- evidence artifact upload.

## Candidate 5/5 result

```text
backend-test                 PASS
frontend-test                PASS
UI-01-CERT browser           PASS
DOCKER-COMPOSE-LOCAL smoke   PASS
S3-CERT structured-agent-cell PASS

CONSENSUS: 5 / 5 GREEN
```

## Certified S3 behavior at this candidate

The candidate demonstrates the following S3 authority:

1. persisted `ContentPlanV1` and frozen `ProfileVersion` are resolved server-side;
2. runtime/model-router readiness is resolved before lifecycle mutation;
3. ContentItem production is claimed atomically from `PLANNED` to `PRODUCING`;
4. Research/Writer/Editor outputs cross typed, versioned, strict contracts;
5. Research `NO_GO`, forbidden/unknown claims, editor rejection and exhausted revision budgets fail closed;
6. provider/model/attempt/digest lineage is durable and tenant-scoped;
7. actual attempt ordinals are preserved across repair/retry lineage;
8. failed and contract-repair attempts are durable evidence, not discarded diagnostics;
9. typed-but-semantically-invalid artifacts preserve their producing attempt and terminalize the GenerationRun as `FAILED`;
10. successful S3 creates a DRAFT `ContentRevisionV1`, binds it to the ContentItem and hands the GenerationRun to `VISUAL_PLANNING`;
11. S3 introduces no S4 visual authority, no S5 rendering authority, no S6 QA authority, no S7 approval authority, and no publication/scheduling side-effect authority;
12. `MK1_STRUCTURED_AGENT_CELL` remains fail-closed and cannot escape the master `MK1_ENABLED` gate.

## Explicit non-claims

This receipt does **not** certify:

- S4 `VisualSpecV1`;
- S5 rendering/AssetStore;
- S6 QA/recovery;
- S7 human approval/ApprovalBundleV2;
- any S3-specific production frontend UI;
- unrestricted external web research capability;
- publication or scheduling authority;
- S2 quality-hardening PR #42.

The generic browser job is retained as a regression gate for the certified S0-S2 product surface; S3 semantic authority is proved by the dedicated S3-CERT gate.

## Superseded diagnostic history

The following historical SHAs/runs are explicitly diagnostic only and cannot substitute for this candidate:

- `3ebe0a66f3711c0f01301095b77163d908e59998` — generic CI green while the S3 production router was not mounted;
- `862f3760fe5be4c7580b4b0ed16b5b91f0e03d05` — first dedicated S3-CERT failed due a brittle route-introspection assertion and initially failed to retain its red-run receipt artifact;
- `bbe4a1f555d626d6e9a1a11420d8bf8d5a8823dc` — dedicated S3-CERT passed, but later pre-freeze audit found attempt ordinal, failed-lineage durability, semantic-failure terminalization and lifecycle-readiness ordering defects;
- `dd3c88425c4734d5e126d98d12941189cf103e88` — implementation/test fixes were present, but pre-freeze documentation reconciliation was not yet complete.

Detailed chronology and corrective actions are preserved in:

```text
mk1/build/slices/S3/ERROR_LEDGER.md
mk1/build/slices/S3/BUILD_RECORD.md
```

## Receipt-head law

This file is the only permitted branch-moving change after candidate freeze.

The commit that introduces this receipt becomes the **receipt head**. Before PR #43 may be marked ready or merged, that exact receipt head must independently pass:

```text
backend-test
frontend-test
UI-01-CERT browser
DOCKER-COMPOSE-LOCAL smoke
S3-CERT structured-agent-cell
```

The merge must use expected-head protection against that exact receipt head. After merge, required main-branch gates must pass before S3 may be declared `CERTIFIED / MERGED`.

## Current decision

```text
CANDIDATE 9d5db5bb375af0522c4d14c946abb70805147d64
EXACT-CANDIDATE GATES  5/5 GREEN
CANDIDATE VERIFIED     YES
RECEIPT HEAD VERIFIED  PENDING
PR #43 READY           NO
MERGE AUTHORIZED       NO
S3 CERTIFIED / MERGED  NO
```
