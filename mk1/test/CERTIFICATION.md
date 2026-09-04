# MK1 Certification Model

Status: **FROZEN**

A green test suite is necessary but not sufficient. Each slice produces a certification record.

## Certification package

```text
slice_id
commit_sha
contract/ADR versions
migration version
unit result
contract result
integration result
E2E result when applicable
visual snapshots when applicable
security/tenant result
chaos/recovery result when applicable
observability evidence
known limitations
rollback procedure
reviewer/acceptance state
```

## Merge gates by slice

Every slice:

- compile/type/lint;
- unit/contract;
- invariant tests;
- documentation/build record updated.

User-facing slice:

- E2E happy/error path;
- accessibility check;
- desktop/mobile visual snapshots.

State/storage slice:

- restart/persistence test;
- migration verification.

Queue/worker slice:

- duplicate/recovery tests;
- lag/DLQ observability.

Publishing slice:

- approval byte verification;
- duplicate-delivery test;
- uncertain crash/reconciliation test;
- mocked provider contract;
- live provider smoke only when authorized credentials/environment exist.

## Release certification

Before MK1 production cutover:

1. fresh environment deploy;
2. bootstrap tenant/profile;
3. generate certified Batch;
4. review/approval;
5. restart durability of approved assets/state;
6. schedule/export;
7. automatic LinkedIn smoke if live credentials authorized;
8. publication receipt or explicitly documented external gate;
9. analytics snapshot where provider capability allows;
10. restart workers and prove no duplicate/lost authority;
11. security tenant tests;
12. rollback/cutover evidence.

## Evidence naming

Store certification records under `mk1/test/evidence/<slice-id>/` or attach CI artifacts referenced from the build record. Large/binary artifacts may live in CI/object storage; repository retains manifest, hashes and canonical links/IDs.

## Failure rule

If certification discovers an invariant violation, the slice is not “mostly done”. Fix/revisit architecture and rerun affected certification.
