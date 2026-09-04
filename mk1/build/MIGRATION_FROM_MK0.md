# MK0 -> MK1 Migration Strategy

Status: **FROZEN PLAN**

## Rule

Migration is incremental authority transfer, not simultaneous rewrite.

## Freeze point

MK0 baseline is the repository state before MK1 design changes (`main` at commit `aa64a49ebf96cfbcd5ef9be015796219ac6a1848` for this design cycle). Preserve a named MK0 ref before runtime migration begins.

## Stage 1 — Bootstrap tenant

Map existing single-admin records to one deterministic/bootstrap Tenant. Do not expose client-selected tenant IDs.

## Stage 2 — Profile bridge

Read MK0 ContentProfile and convert to ProfileVersionV2 representation through an explicit adapter/migration. Preserve original version and migration provenance.

No secret migration into Profile.

## Stage 3 — New planning authority

New MK1 Create requests produce Batch + ContentItems. MK0 generation endpoints remain available behind a legacy flag until MK1 production cell certifies.

## Stage 4 — Structured production

MK1 ContentItems produce GenerationRuns/Revisions. Existing ContentRuns remain historical; do not attempt to pretend old string outputs were typed contracts they never were.

Historical UI may label them `MK0 legacy run`.

## Stage 5 — Approval authority

New MK1 revisions use ApprovalBundleV2. MK0 approvals remain valid historical evidence for MK0 publication records. Do not rewrite old bundle digests into a new algorithm.

## Stage 6 — Scheduling/publishing authority

After Redis/outbox/adapter certification, new MK1 schedules use the new Schedule/Publication entities. Disable MK0 scheduler writes for MK1 content before enabling MK1 worker publication.

One item must never be schedulable through both paths simultaneously.

## Stage 7 — Legacy projections

Stop writing legacy `posts` projection when all active UI/read paths use MK1 entities and data retention/export requirements are met.

## Stage 8 — Cleanup

Remove dead MK0 compatibility code only after:

- production cutover receipt;
- rollback window expires;
- historical data remains readable/exportable;
- no active flag references the path.

Cleanup is a separate PR/slice from functional cutover.
