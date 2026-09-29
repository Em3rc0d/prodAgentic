# prodAgentic MK1

MK1 is the active reconciled generation of prodAgentic.

## Canonical branch authority

```text
main
  └─ stable/certified product authority

developer
  └─ active brainstorming → design → architecture → plan → build → test
```

Historical branches and PRs are audit/archive evidence only unless explicitly reactivated by a documented decision.

## Current generations

- **MK0** — historical implementation lineage and evidence source.
- **MK1** — current product generation.

## Current release state

- `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e` — latest stable certified authority (MK1-R3).
- `developer` — MK1-R4 Creative Production, design/implementation hardening, **NOT CERTIFIED**.

R4 exists to close the gap between a technically governed pipeline and a product that consistently produces complete, profile-driven, publishable editorial packages with real visual output.

## MK1 method

```text
brainstorming
    ↓
design
    ↓
architecture
    ↓
plan
    ↓
build
    ↓
test
    ↓
certification
    ↓
learning / next cycle
```

The process is cyclical, not terminal. Outcomes feed evidence, editorial memory and the next planning cycle.

## Directory authority

```text
brainstorming/  exploration and hypotheses; never authoritative by itself
design/         product, UX and visual behavior contracts
arch/           domain, application, infrastructure and invariants
plan/           dependency graph, delivery order, risks and gates
build/          implementation records, candidate/error ledgers, repository hygiene
test/           acceptance criteria, golden datasets and certification evidence
mining-site/    external/internal evidence intake with provenance
quarries/       scoped investigations that may promote findings upstream
```

## R4 canonical reading order

1. `mk1/STATUS.md`
2. `mk1/build/REPOSITORY_HYGIENE.md`
3. `mk1/build/r4/README.md`
4. `mk1/build/r4/ARCHITECTURE.md`
5. `mk1/build/r4/BUILD_RECORD.md`
6. `mk1/build/r4/ERROR_LEDGER.md`
7. `mk1/plan/R4_EXECUTION_PLAN.md`
8. `mk1/test/R4_ACCEPTANCE.md`
9. `mk1/mining-site/R4_RESEARCH_LEDGER.md`
10. `mk1/build/r4/CERTIFICATION_GRAPH.json`

## Reciprocal validation model

R4 treats the product as a linked authority graph rather than unrelated pipeline stages. Each durable node validates the authority it consumed and must be traceable into the next decision/artifact. The operational loop closes through analytics, editorial memory and learning proposals into subsequent planning/profile decisions.

Machine-readable graph integrity is checked by:

```bash
python scripts/verify_r4_cert_graph.py
```

Candidate/release mode may additionally require digests:

```bash
python scripts/verify_r4_cert_graph.py --require-digests
```

The structural verifier is only one gate. It cannot certify editorial quality, provider behavior, build provenance or product publishability by itself.

## Documentation precedence

When active MK documents conflict:

```text
accepted ADR / invariant
        >
architecture contract
        >
design contract
        >
plan
        >
build note
        >
brainstorming / quarry finding
```

Certification receipts and exact-SHA evidence determine whether a release actually crossed its gates.

## Release law

A candidate is an exact SHA on `developer`; no disposable candidate branch is required.

```text
developer@candidate
      ↓
exact-head PRE-CERT
      ↓
real-profile/product UAT
      ↓
merge to main
      ↓
exact-main POST-CERT
      ↓
release receipt
```

Failed SHAs remain immutable evidence. No documentation or later fix can relabel a failed candidate as certified.

## Build authorization phrase

MK1 uses **“Take the hummer”** to mean the current graph is sufficiently closed to enter a build phase. It never bypasses exact-SHA verification, human authority, product-quality UAT or post-merge certification.
