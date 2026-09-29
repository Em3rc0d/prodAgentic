# R4.1 implementation handoff

Status: **READY FOR JETT AUDIT** after publication of this commit. This is an
implementation handoff, not a runtime, editorial or release certification.

- Repository: `Em3rc0d/prodAgentic`
- Base SHA: `dc9e072846b94b6476ff8c246e83388df10dad7b`
- Branch: `r4.1-reliability-evidence-authority`
- Final SHA: the commit containing this handoff (reported exactly in the delivery message).
- Protected branches: main, developer and r4-final-execution were not modified.
- No PR was merged and no cloud deployment was performed.
- Restart preflight: GitHub confirmed the target branch absent and
  r4-final-execution still at the exact baseline. An unpublished local draft was
  recovered as input, reapplied in a clean baseline checkout, and reviewed against
  every implementation block; no previous delivery or runtime evidence was assumed.

## Contracts and implementation

Added EvidenceProvenanceV1, EvidenceSourceV1, EvidenceBundleV1,
EvidenceAcquisitionPort, ProductionRecoveryAction, RecoveryDecisionV1,
ReplacementPlanV1 and RecoveryRepositoryPort. ResearchPackV1 now binds optional
bundle identity/digest while retaining historical serialization without those
fields. GenerationRunV1 adds acquisition state, retry predecessor and bundle
identity/digest. GenerationFailureV1 carries a durable recovery action.

The production factory requires evidence acquisition. Native Gemini Search
metadata is normalized into bounded secondary evidence with content hashes;
provider responses are never persisted wholesale. Exact evidence enters Research
input hashes and claim-binding validation. QA and approval verify it independently.
A provider-grounded summary is not an independently verified source quotation.

Routing now separates stage, route and attempt deadlines, reserves time and
attempts for fallback, keeps transport/language/contract repair budgets distinct,
and shares the stage clock across contract repairs. Model timeout and stage
exhaustion remain distinct. Google quota is model-scoped; n8n no-bypass and
request-local isolation remain. Structured language validation selects prose fields
and checks substantial individual fields as well as the aggregate.

Transient text recovery creates a new run from the same frozen profile/plan,
reusing intact unexpired evidence. Semantic failure uses a replacement candidate
from the governed pool, fresh memory/novelty checks, a new item/plan and a durable
CAS-appended replacement ledger. Historical failed runs are not reopened. Open
render work can resume from a verified saved revision. UI actions reflect those
semantics and reload via the batch URL; API errors expose safe operational details.

ARCHITECTURE.md and README.md describe the implemented behavior and limitations.
CERTIFICATION_GRAPH.json includes reciprocal evidence and replacement edges;
certification digests remain null. New planning trace hashes use typed JSON and
preserve timestamps so replacement can verify exact trace authority.

## Requirement-to-code map

| Contract block | Implementation ownership |
| --- | --- |
| Evidence authority and claim binding | domain/production/evidence.py; infrastructure/evidence/google_grounding.py; structured_text.py; production/service.py |
| Routing/time budget | agents/router.py; core/execution_budget.py; StructuredRouterExecutor |
| Structured language validation | core/validator.py |
| Recovery model | application/production/recovery.py; domain/production/recovery.py; infrastructure/mongo/recovery.py |
| Failure taxonomy | domain/production/failures.py; GenerationFailureV1 |
| Safe observability | production/service.py; routes/production.py; routes/rendering.py |
| UI recovery | Mk1BatchCreate.tsx; lib/r2-production.ts |
| Reciprocal lineage | load_run_evidence; QA and approval services; typed ReplacementPlanV1 |
| Security/privacy | bounded normalization; safe error allowlist; existing scoped repositories/auth/CSRF |
| Documentation | ARCHITECTURE.md; README.md; CERTIFICATION_GRAPH.json; this handoff |

All backend paths above are relative to backend/; frontend names refer to the
changed-file list below. The map describes implementation ownership, not passing
acceptance results.

## Implementation limits for the independent audit

1. No runtime behavior has been tested in this handoff. Existing R4.1 service
   fixtures must supply an evidence provider; older fixtures lacking router policy
   or expecting the previous routing taxonomy may need deliberate updates by Jett.
2. Only native Google grounding is implemented. n8n evidence acquisition remains
   unavailable when direct fallback is forbidden; this stops with an explicit code.
   No new external service subscription/credential is required, but Gemini Search
   has provider usage charges/quotas and provider-specific terms to assess in UAT.
3. Source IDs and hashes establish lineage, not factual truth. Grounding coverage,
   semantic entailment, hallucination resistance and final editorial quality remain
   audit/UAT concerns. Full pages, raw responses and Search widget HTML are not saved.
4. Replacement is bounded by the original candidate pool, novelty policy and a
   120-entry batch ledger. Pool exhaustion or invalid historical trace digest stops
   safely. Old BSON timestamp precision loss is not repaired by rewriting history.
5. A process crash between item claim and run creation still requires operator
   reconciliation. The 150-second inherited budget bounds provider stages, not
   database outages or arbitrary process death. A distributed worker lease was not
   introduced. Terminal contract/integrity failures require operator attention.
6. Static Python/TypeScript syntax inspection and diff/whitespace review were the
   only code checks performed. No application was imported, started or exercised.

## Required execution declarations

```text
TESTS NOT EXECUTED
CI NOT EXECUTED
UAT NOT EXECUTED
BROWSER VALIDATION NOT EXECUTED
CERTIFICATION NOT CLAIMED
MAIN NOT MODIFIED
DEVELOPER NOT MODIFIED
R4-FINAL-EXECUTION NOT MODIFIED
```

## Changed files

- `backend/agents/router.py`
- `backend/application/approval/service.py`
- `backend/application/planning/service.py`
- `backend/application/production/lifecycle.py`
- `backend/application/production/r4_service.py`
- `backend/application/production/recovery.py`
- `backend/application/production/service.py`
- `backend/application/quality/execution.py`
- `backend/core/execution_budget.py`
- `backend/core/validator.py`
- `backend/db/mongo.py`
- `backend/domain/production/evidence.py`
- `backend/domain/production/failures.py`
- `backend/domain/production/models.py`
- `backend/domain/production/ports.py`
- `backend/domain/production/recovery.py`
- `backend/infrastructure/agents/structured_text.py`
- `backend/infrastructure/evidence/__init__.py`
- `backend/infrastructure/evidence/google_grounding.py`
- `backend/infrastructure/mongo/planning.py`
- `backend/infrastructure/mongo/production.py`
- `backend/infrastructure/mongo/recovery.py`
- `backend/routes/batches.py`
- `backend/routes/production.py`
- `backend/routes/rendering.py`
- `frontend/components/mk1/Mk1BatchCreate.tsx`
- `frontend/components/mk1/mk1-batch-create.module.css`
- `frontend/lib/mk1-batches.ts`
- `frontend/lib/r2-production.ts`
- `mk1/build/r4/ARCHITECTURE.md`
- `mk1/build/r4/CERTIFICATION_GRAPH.json`
- `mk1/build/r4/R4_1_HANDOFF.md`
- `mk1/build/r4/README.md`
