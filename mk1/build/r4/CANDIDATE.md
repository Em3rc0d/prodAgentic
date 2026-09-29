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

## Profile authority law

Legacy Profile repair is conditional, not a release-version bump.

- If the selected real ProfileVersion contains malformed legacy authority eligible under `r4-profile-upgrade-v1`, the operator must inspect the proposal and explicitly accept or reject it. Acceptance creates the next immutable ProfileVersion and preserves the historical version.
- If the selected real ProfileVersion is already clean and no legacy repair proposal exists, certification records `NO_UPGRADE_REQUIRED` and freezes that exact current ProfileVersion. A synthetic version bump is forbidden.
- Final UAT is always bound to the exact frozen ProfileVersion identity and digest actually used by Planning.

The final Em3rc0d authority diagnostic before this reconciliation observed:

```text
CURRENT_VERSION=1
CURRENT_DIGEST=6c24104a9df55df10c55dd1affb6d28672139ca7ff3da0ba2c3ee90348f45c20
PROVENANCE=USER_ACCEPTED
CURRENT_HAS_MALFORMED_TOPIC=false
LEGACY_TENANT_COUNT=0
LEGACY_MATCH_COUNT=0
AUTHORITY_CLASS=CURRENT_V1_CLEAN_NO_MATCHING_LEGACY_SOURCE
R4_PROFILE_GATE=NEEDS_PROTOCOL_RECONCILIATION
```

That evidence means Em3rc0d v1 remains the correct authority unless later evidence shows the Profile itself changed through an explicit user-authorized semantic edit.

## Final R4.1 promotion protocol

```text
PR #69 exact head SHA
        ↓
automated PRE-CERT + supply-chain audits
        ↓
inspect exact real Profile authority
        ↓
legacy malformed and upgrade-eligible?
        ├─ YES → explicit human decision → accepted vN+1 or rejected
        └─ NO  → record NO_UPGRADE_REQUIRED
        ↓
freeze exact immutable ProfileVersion + digest
        ↓
fresh production/non-demo exact-ProfileVersion ×4
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
