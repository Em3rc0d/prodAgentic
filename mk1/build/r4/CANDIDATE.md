# R4 Candidate Protocol

Status: **NO CANDIDATE FROZEN**

## Branch model

R4 uses only:

- `developer` — active design/build/test authority.
- `main` — stable certified authority.

No candidate branch is required. A candidate is an **exact immutable SHA** from `developer` recorded here with its evidence.

## Freeze conditions

A candidate SHA may be recorded only when:

1. R4 architecture, plan, build record, error ledger and acceptance criteria agree on scope.
2. No known BLOCKER is hidden or mislabeled.
3. Unit/integration/regression suites pass locally or in a reproducible CI environment.
4. The certification graph verifier passes structurally.
5. Real-provider UAT prerequisites are available or explicitly recorded as an external gate.
6. The working tree represented by `developer` is the exact code intended for certification.

## Candidate record template

```text
Candidate ID: R4-C<n>
SHA: <40-hex>
Parent stable authority: main@<sha>
Frozen at: <UTC timestamp>
State: FROZEN | REJECTED | PRE-CERTIFIED | MERGED | POST-CERTIFIED

Required checks:
- backend unit/integration
- frontend unit/build
- browser journey desktop/mobile
- renderer/asset ownership
- QA recovery/restart
- novelty/memory
- strict editorial publishability
- generated-image fake-provider regression
- bounded real-provider UAT
- full historical regression
- certification graph structural verifier
- exact-SHA workflow/check receipt
```

## Exact-SHA law

Any tracked mutation after freeze creates a different candidate. Failed candidate SHAs remain immutable historical evidence and are never re-described as certified after fixes land elsewhere.

## Promotion protocol

```text
developer@CANDIDATE_SHA
        ↓
exact-head PRE-CERT
        ↓
product UAT receipt
        ↓
merge developer → main
        ↓
MAIN_MERGE_SHA
        ↓
exact-main POST-CERT
        ↓
release receipt
        ↓
developer resumes from certified main lineage
```

The merge itself is not certification. Post-merge verification must bind evidence to the exact `main` SHA.

## Current R4 candidate ledger

No candidate is frozen. The current development head is allowed to change while design/hardening continues.
