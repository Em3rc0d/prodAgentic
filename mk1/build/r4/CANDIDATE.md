# R4 Candidate Protocol

Status: **PRE-UAT CANDIDATE ACTIVE / NOT CERTIFIED**

## Authority model

R4 product authority remains:

- `main` — stable certified product authority;
- `developer` — integration authority.

The independent R4.1 audit uses PR #69 from temporary branch `r4.1-reliability-evidence-authority` so `main` and `developer` can remain untouched during adversarial certification. This is an explicit audit exception, not a third product-authority branch.

A candidate is always an **exact immutable SHA**. For the active R4.1 audit, the exact candidate identity is the current PR #69 head recorded by GitHub and by every exact-SHA workflow receipt. This file deliberately does not embed its own commit SHA because a Git commit cannot truthfully contain its final self-hash.

## Freeze conditions

A candidate may enter fresh UAT only when:

1. R4 architecture, plan, build record, error ledger and acceptance criteria agree on scope.
2. No known BLOCKER is hidden or mislabeled.
3. Unit/integration/regression suites pass against the exact candidate.
4. The certification graph verifier passes structurally.
5. Locked backend dependencies pass `pip-audit`.
6. The complete frontend dependency graph passes `npm audit --audit-level=high`.
7. exact-SHA Docker/renderer/Redis/frontend closure gates pass.
8. real-provider UAT prerequisites are available.
9. `main` and `developer` remain unchanged until promotion is explicitly authorized.

## Required pre-cert evidence

```text
backend full regression
frontend lint/unit/build
browser journey
renderer + asset ownership
QA recovery/restart
novelty/memory
strict editorial publishability
generated-image recovery
real Redis delegated regression
pip-audit
npm audit
certification graph
exact-SHA workflow metadata
fresh production/non-demo real-provider UAT
human editorial 4/4
```

## Exact-SHA law

Any tracked mutation after freeze creates a different candidate. Failed candidate SHAs remain immutable historical evidence and are never re-described as certified after fixes land elsewhere.

## Final R4.1 promotion protocol

```text
PR #69 exact head SHA
        ↓
automated PRE-CERT + supply-chain audits
        ↓
Profile v1 → explicit Profile v2 acceptance
        ↓
fresh production/non-demo Profile-v2 ×4
        ↓
4/4 Reviewable
        ↓
human editorial PASS ×4
        ↓
repository protection/required-check gate
        ↓
explicit merge authorization
        ↓
merge to main
        ↓
exact MAIN_MERGE_SHA POST-CERT
        ↓
release receipt
```

The merge itself is not certification. Post-merge verification must bind evidence to the exact `main` SHA.

## Current ledger rule

The active candidate is whatever exact SHA GitHub reports as PR #69 head **after all tracked changes have settled and all required pre-UAT workflows pass**. The PR body carries failed-candidate lineage and exact run IDs. No older green SHA may substitute for the current head.
