# S7 BUILD RECORD — Review + ApprovalBundleV2

Status: IMPLEMENTATION CANDIDATE / CERTIFICATION REQUIRED

## Objective

Transfer human review/approval authority into MK1 without giving S7 export, scheduling or publication authority.

## Accepted design authority

- `mk1/plan/VERTICAL_SLICES.md` — S7 Review + ApprovalBundleV2.
- `mk1/design/REVIEW.md` — progressive disclosure and explicit Approve/Edit semantics.
- `mk1/arch/ADR-0008-IMMUTABLE-APPROVAL.md` — exact immutable human approval.
- `mk1/arch/INVALIDATION_RULES.md` — edits create revision and invalidate only downstream authority.
- `mk1/arch/STATE_MACHINES.md` — Revision remains REVIEWABLE; Approval is a separate aggregate.

## Authority boundary

```text
S6 REVIEWABLE revision
        ↓
ReviewAuthoritySnapshotV1
        ↓ exact review_digest
explicit authenticated human Approve
        ↓
restart-safe approval reservation
        ↓
re-read owned AssetStore bytes + SHA-256
        ↓
immutable ApprovalBundleV2
        ↓
ContentItem APPROVED + latest_approval_id

S8+ export / scheduling / publication: NOT OWNED BY S7
```

## New modules

- `backend/domain/approval/`
- `backend/application/approval/`
- `backend/infrastructure/mongo/approval.py`
- `backend/routes/approval.py`
- `frontend/lib/approval.ts`
- S7 Review actions in `frontend/app/review/[revisionId]/`

## Persistence

Collections:

- `approval_bundles` — immutable ApprovalBundleV2, unique by tenant+approval_id and tenant+revision_id.
- `approval_reservations` — internal crash/concurrency reservation, unique by tenant+revision_id.

The reservation fixes the process-death boundary between user intent and immutable bundle persistence. Retry of the same review digest + actor reopens the same reservation; a competing review intent is rejected.

## Exact approval authority

Approval requires all of the following to still agree at action time:

- current ContentItem revision;
- `ContentRevision.REVIEWABLE`;
- completed GenerationRun;
- frozen ProfileVersion digest;
- ContentPlan digest;
- ResearchPack digest;
- ContentSpec digest;
- VisualSpec digest when applicable;
- exact QAReport digest and non-FAIL verdict;
- exact owned AssetV1 IDs/SHA-256 values;
- fresh read-back byte length and SHA-256 from AssetStore.

The Review GET returns `review_digest`; POST Approve must present that digest. Any authority change makes the request stale and blocks approval.

## Edit semantics

S7 never rewrites a reviewable/approved revision in place.

Human Edit creates:

- a new `GenerationRunV1` lineage;
- a new `ContentSpecV1` identity;
- a child `ContentRevisionV1` with `source=HUMAN_EDIT` and `parent_revision_id`;
- explicit invalidation evidence;
- no inherited QA/Approval authority.

When changed copy is not referenced by editorial-critical VisualSpec blocks, S7 clones the immutable visual intent onto the new revision and invalidates Assets+QA. When visual-critical copy changes, VisualSpec/Assets/VisualQA are invalidated and the new revision returns to visual planning.

## UX

Default Review shows content quality and small deliberate actions:

- Approve
- Edit / Create revision

QA/digests/correlation evidence remain under `Why / Details`. Mobile actions remain sticky. S5/S6 behavior remains fail-closed when S7 is disabled or the Review authority endpoint is unavailable.

## Failure paths

- stale review digest → 409 conflict;
- current revision changed → 409 conflict;
- missing/corrupt frozen artifact → approval blocked;
- post-QA asset byte/hash drift → approval blocked;
- competing reservation → conflict;
- process death after reservation/bundle persistence → idempotent restart path;
- edit never mutates source revision.

## Tests / certification

Dedicated workflow: `.github/workflows/s7-cert.yml`.

Required gates:

1. exact Review digest + owned-byte rehash + immutable bundle tests;
2. stale approval and post-QA tamper rejection;
3. Human Edit creates a child revision;
4. real Mongo restart/reservation/concurrency/tenant/CAS tests;
5. AST boundary proves no S8+ export/scheduling/publication authority;
6. production frontend build;
7. desktop/mobile Playwright Review Approve/Edit progressive disclosure;
8. existing CI, Docker, S3, S4, S5 and S6 remain green on the same candidate SHA.

## Rollback

Disable `MK1_REVIEW_APPROVAL`. S5/S6 Review preview remains available; immutable S7 approval evidence already created remains historical and is never rewritten.

## Known limitations

S7 does not export, schedule or publish. Those remain S8+ slices by frozen design.
