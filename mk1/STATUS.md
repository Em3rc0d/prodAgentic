# prodAgentic MK1 Status

**As of:** 2026-09-06  
**Stage:** IMPLEMENTATION — S0/S1/S2 CERTIFIED AND MERGED  
**Current operator gate:** LOCAL ACCEPTANCE OF THE S0→S2 PRODUCT SURFACE  
**Next planned implementation slice:** S3 — Structured Agent Cell (not present on the certified product baseline)

## Canonical product baseline

The exact **certified product-code baseline** through S2 is:

```text
002177e90431d6009498a88cc6eb20efc46e14b3
```

That commit is `MK1 S2: Batch planning, editorial memory and novelty (#37)` and preserves the exact certified S2 receipt head as its second parent.

Post-merge CI on that exact product SHA is green:

```text
CI run: 33982022917
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

Documentation-only descendants may advance `main` without replacing this product certification boundary. A documentation commit is not a new product-code certificate.

For local acceptance, record the exact `HEAD` you test and verify that the certified product baseline above remains an ancestor. If commits after the product baseline modify runtime/product code, they require their own certification before they can inherit this acceptance authority.

## MK1 certification ledger

### Design Freeze

- reviewed design head: `730c2f89ec6527031dc95d0e4fbf86c981a41b6f`
- Design Freeze PR: `#32`
- canonical design merge: `2211ffe5123fbf2d23d6b88ba3cd0257f569b5d1`
- Build Entry receipt: `mk1/plan/BUILD_ENTRY_RECEIPT.md`
- build authorization phrase: `TAKE THE HUMMER`

### S0 — Foundation + Bootstrap Tenant

State: **CERTIFIED / MERGED**

```text
reviewed code head: 74056ec8930aecd61ad771da94076046dc95a9c8
CI run:             33892749948 / #677
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

S0 established the server-owned tenant boundary, tenant-scoped repositories, additive/idempotent bootstrap migration and the gated MK1 shell without transferring authority from unfinished slices.

Certified S0 merge used by S1:

```text
88a615c519b5918944256afd678b67139ed8f0bd
```

### S1 — Profile V2

State: **CERTIFIED / MERGED**

```text
certified candidate: b7b821691da6fe8375109ab00e6eb08c4858e5b4
CI run:             33928753075 / #689
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

S1 closed the low-friction Profile V2 proposal/acceptance flow, immutable ProfileVersion history, exact acceptance digests, restart recovery for interrupted profile updates, tenant isolation, allowlisted migration and the structural secret/OAuth boundary.

Certified S1 merge used by S2:

```text
bfa64cb7e03e2344be80a789f0871bbac2bbbcea
```

### S2 — Batch + Editorial Memory + Novelty

State: **CERTIFIED / MERGED / POST-MERGE GREEN**

Implementation candidate:

```text
3aa962e0d1bd378a3fa0eaa1b252dcd0a69affa2
```

Code-candidate evidence:

```text
CI run:             33981477379 / #698
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

Exact certification receipt head:

```text
59d45a9dede3fd65246f4bba40707d707d4deea2
```

Receipt-head canonical CI:

```text
CI run:             33981751709
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

Merge/product baseline:

```text
002177e90431d6009498a88cc6eb20efc46e14b3
```

Post-merge exact-product CI:

```text
CI run:             33982022917
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

Detailed post-merge receipts:

- `mk1/build/slices/S2/POST_MERGE.md`
- `mk1/test/evidence/S2/POST_MERGE_RECEIPT.md`

S2 introduces first-class Batch planning, rebuildable Editorial Memory, explainable Novelty, immutable ContentPlanV1 evidence and the low-friction `/create` cockpit. S2 intentionally does **not** invoke the S3 Research/Writer/Editor/Visual production cell and does not publish externally.

## Product surface authorized for local acceptance

With MK1 S0/S1/S2 feature flags enabled:

```text
bootstrap tenant
    ↓
MK1 shell
    ↓
/profiles
    ↓
Profile V2 proposal
    ↓
explicit acceptance
    ↓
immutable ProfileVersion
    ↓
/create
    ↓
Profile selector
    ↓
Tomorrow / This week
    ↓
1 / 4 / 7 requested pieces
    ↓
Generate next batch
    ↓
Editorial Memory refresh
    ↓
oversized candidate pool
    ↓
Novelty + diversity selection
    ↓
ContentPlanV1 evidence
    ↓
Batch + ContentItems
```

Expected operator-visible behavior:

- Profile setup is low-friction and does not expose model/agent controls.
- Proposal review occurs before immutable ProfileVersion creation.
- Batch planning reports `selected/requested` honestly.
- Insufficient novelty may return fewer items than requested; standards are not silently relaxed.
- Planning evidence is progressively disclosed rather than permanently expanded.
- The exact ProfileVersion used for planning is frozen into Batch/ContentItem/ContentPlan evidence.
- S2 planning remains provider-free/deterministic with respect to semantic novelty evaluation.
- No S3 production cell or external publication should occur during this acceptance pass.

Important UI boundary: S2 currently shows the newly planned Batch in `/create`, but it does not yet provide a Batch-history browser. Historical/freeze verification therefore uses the certified read-only Batch API `GET /api/batches/{batch_id}` as evidence; the acceptance checklist states this explicitly rather than pretending a history UI exists.

## Feature gates for S0→S2 local acceptance

Backend:

```text
MK1_ENABLED=true
MK1_PROFILE_V2=true
MK1_BATCH_PLANNING=true
```

Frontend:

```text
NEXT_PUBLIC_MK1_SHELL=true
NEXT_PUBLIC_MK1_PROFILE_V2=true
NEXT_PUBLIC_MK1_BATCH_PLANNING=true
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Defaults remain off in checked-in runtime examples so incomplete/future authority is never enabled implicitly.

## Local acceptance authority

Canonical setup guide:

- `docs/LOCAL_DEVELOPMENT.md`

Operator acceptance checklist:

- `mk1/test/LOCAL_ACCEPTANCE.md`

Run acceptance from synchronized `main`, record the exact tested `HEAD`, and verify:

```bash
git merge-base --is-ancestor 002177e90431d6009498a88cc6eb20efc46e14b3 HEAD
```

For a documentation-only descendant, review:

```bash
git diff --name-only 002177e90431d6009498a88cc6eb20efc46e14b3..HEAD
```

No un-certified runtime/product-code mutation may be hidden inside that descendant range.

## What local acceptance does and does not prove

Local acceptance can prove:

- the certified code starts correctly on the operator machine;
- Mongo persistence works in the operator environment;
- S0 tenant bootstrap and auth/session behavior are usable locally;
- S1 Profile V2 UX/API behavior is usable locally;
- S2 Create/Batch/Memory/Novelty behavior is usable locally;
- the product surface matches the intended low-friction interaction model.

Local acceptance does **not** by itself prove:

- S3+ generation behavior;
- production deployment readiness;
- production OAuth/LinkedIn behavior;
- production backups/restores;
- multi-user/RBAC readiness;
- publication authority beyond already-certified MK0 paths;
- commercial release readiness.

## Open repository hygiene

Historical draft PR `#27` (`RECONCILE-01`) predates the canonical MK1 slice line. It is not authority for S0/S1/S2 local acceptance and must not be merged into the current MK1 line without explicit reconciliation against accepted MK1 architecture/invariants.

## Next executable graph

```text
DESIGN FREEZE                    ✅ CLOSED
        ↓
S0 FOUNDATION                    ✅ CERTIFIED / MERGED
        ↓
S1 PROFILE V2                    ✅ CERTIFIED / MERGED
        ↓
S2 BATCH + MEMORY + NOVELTY      ✅ CERTIFIED / MERGED
        ↓
S0→S2 LOCAL OPERATOR ACCEPTANCE  ⏳ READY TO EXECUTE
        ↓
S3 STRUCTURED AGENT CELL         ○ NEXT PLANNED SLICE
```

The local acceptance gate is intentionally between S2 and the next product expansion so usability/environment defects are discovered before more execution machinery is layered on top.
