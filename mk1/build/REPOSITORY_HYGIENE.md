# MK1 Repository Hygiene

Status: **ACTIVE POLICY — S4 ENTRY**  
Last reconciled: 2026-09-08

## Purpose

Keep the repository readable for humans and agents without destroying audit evidence. Branch/PR cleanup must never be used to hide failed candidates, bypass exact-SHA certification, or merge obsolete authority into the current MK1 line.

## Canonical branch model

```text
main
  └─ only merged/certified product work or explicitly bounded documentation descendants

mk1/sN-<slice>
  └─ one active implementation line for the current slice

<temporary docs/fix branch>
  └─ short-lived, merged through a PR, then eligible for deletion
```

There is currently **no `developer` / `develop` branch**. Do not create one merely for symmetry. If a development integration branch is introduced later, it requires an explicit workflow decision and documented merge authority. Until then, `main` is the only integration authority and active slice branches start from its exact SHA.

## Preservation rule

A branch may be deleted after its useful commits are reachable from `main` **or** after its PR is explicitly archived/superseded and the reason is recorded. Deleting a branch ref does not delete Git/PR history; failed candidates and certification evidence remain part of the audit trail.

Never force-rewrite a historical certified branch just to make the branch list look clean.

## Current canonical anchors

```text
S3 product certificate:
a10dfec7f5851ae3f8c850fcc934009951f7d422

S3 final documentation descendant / current pre-S4 main:
2dd152e671667e1377907c53748aec83aaf4796b
```

S3 product authority remains bound to the product certificate SHA; the later documentation merge does not replace that boundary.

## Archived open lines closed before S4

### PR #42 — `mk1/s2-quality-hardening`

Disposition: **CLOSED / NOT MERGED / PRESERVED AS DIAGNOSTIC DEBT**.

Reason:
- based on the old S2-era main;
- intentionally excluded from the certified S3 lineage;
- never achieved its required exact-head browser certificate;
- cannot be promoted after S3 by silently merging stale code.

The operator-found topic-authority problem remains valuable product evidence. If revisited, re-derive the fix from current `main` under a new bounded slice/PR and certify it there.

### PR #27 — `reconcile/commercial-v1-main-first`

Disposition: **CLOSED / NOT MERGED / HISTORICAL RECONCILIATION ARCHIVE**.

Reason:
- predates canonical MK1 slice authority;
- contains a large historical reconciliation line with assumptions superseded by S0→S3;
- merging it wholesale would contaminate the exact certification chain.

Useful ideas/code may be mined from it, but only through current design/architecture contracts and a new certified slice.

## Branch cleanup classes

### KEEP

- `main` — canonical integration branch.
- `mk1/s4-visualspec-v1` — active S4 implementation branch once rebased/advanced to the final S4-entry main.
- `mk0/freeze-20260831` — historical generation freeze anchor; keep unless replaced by an immutable tag/archive policy.

### ELIGIBLE FOR DELETION AFTER MERGE/ARCHIVE VERIFICATION

Historical feature, fix, docs, ops, release and completed MK1 slice branches whose accepted work is already reachable from `main`, including completed S0/S1/S2/S3 and their merged documentation/fix branches.

Representative prefixes:

```text
feat/*
fix/*
hotfix/*
ops/*
docs/*
release/*
security/*
mk1/s0-*
mk1/s1-*
mk1/s2-batch-*
mk1/s3-*
mk1/build-entry-*
mk1/design-freeze-*
mk1/work-execution-directive-*
```

Before deleting any individual ref, verify one of:

```bash
git merge-base --is-ancestor origin/<branch> origin/main
```

or an explicit archived/superseded PR disposition exists.

### ARCHIVE / DO NOT MERGE

```text
mk1/s2-quality-hardening
reconcile/commercial-v1-main-first
```

Their branches may be deleted only after preserving the PR/ledger references; their code is not current authority.

## Pull-request hygiene

At S4 entry there should be no unexplained open historical PRs. A PR may be open only when it is:

1. the current active slice;
2. an intentionally isolated bounded fix with its own certification line; or
3. a short-lived documentation descendant.

Draft status never substitutes for a documented disposition.

## Slice branch law

For S4:

```text
main@S4_ENTRY_SHA
  ↓
mk1/s4-visualspec-v1
  ↓
implementation + BUILD_RECORD + ERROR_LEDGER + tests
  ↓
freeze one exact candidate SHA
  ↓
required exact-SHA gates
  ↓
receipt-only head
  ↓
exact-head merge
  ↓
post-merge gates
```

No unrelated repository-cleanup changes should be mixed into the frozen S4 product candidate after this entry reconciliation.

## Tooling note

Repository policy distinguishes **merging/archiving** from **deleting remote refs**. If the connected GitHub automation surface cannot delete branch refs, deletion is a final mechanical repository-admin action after the verification list above; it must not be simulated by force-moving old refs to `main`, because that would destroy useful lineage.
