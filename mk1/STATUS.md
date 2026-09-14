# prodAgentic MK1 Status

**As of:** 2026-09-13  
**Stable authority:** `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e` — MK1-R3 certified  
**Development authority:** `developer` — MK1-R4 Creative Production  
**R4 state:** DESIGN + IMPLEMENTATION HARDENING / NOT CERTIFIED

## Canonical branch model

```text
main
  └─ stable/certified authority only

developer
  └─ active brainstorming → design → architecture → plan → build → test
```

No other branch is current product authority. Historical refs remain audit/archive material only.

## Current stable product boundary

R3 remains the latest certified product authority on `main`:

```text
790f1e86312e13f4b14f1320db5d83f94ed8a97e
```

R4 is not allowed to inherit the word “certified” from R3 merely because it descends from it.

## R4 objective

R4 closes the remaining gap between a governed technical content pipeline and a governed creative-production system capable of producing complete, profile-driven, publishable editorial packages with real visual production.

Canonical R4 authority:

- `mk1/build/r4/README.md`
- `mk1/build/r4/ARCHITECTURE.md`
- `mk1/build/r4/BUILD_RECORD.md`
- `mk1/build/r4/ERROR_LEDGER.md`
- `mk1/build/r4/CANDIDATE.md`
- `mk1/build/r4/CERTIFICATION_GRAPH.json`
- `mk1/plan/R4_EXECUTION_PLAN.md`
- `mk1/test/R4_ACCEPTANCE.md`
- `mk1/mining-site/R4_RESEARCH_LEDGER.md`
- `scripts/verify_r4_cert_graph.py`

## R4 validation model

R4 uses a reciprocal validation graph rather than isolated pipeline stages:

```text
ProfileVersion
  ↕
CreativeBrief
  ↕
CandidatePool / EditorialMemory
  ↕
ContentPlan
  ↕
ResearchPack
  ↕
ContentSpec
  ↕
EditorialGate
  ↕
VisualSpec
  ↕
Owned Source Assets
  ↕
Rendered Assets
  ↕
Visual QA
  ↕
Human Review
  ↕
ApprovalBundle
  ↕
Export / Publication
  ↕
Analytics / Learning
  ↕
EditorialMemory / next planning cycle
```

The machine-readable graph must contain reciprocal predecessor/successor edges and no orphan start/end nodes. Candidate mode additionally requires digest/evidence population.

## R4 implemented but uncertified

- model-backed creative candidate generation for production mode;
- deterministic novelty/memory/diversity planning authority;
- Profile-derived CreativeBrief;
- strict R4 editorial publishability gate;
- demo/production separation;
- generated-image requirement and provider adapter path;
- product-owned generated source assets with SHA lineage;
- Chromium composition with resolved local/data-backed imagery;
- QA reconstruction from persisted source lineage;
- Review visual-board improvements.

## R4 blocking work

R4 remains open until all blockers in `mk1/build/r4/ERROR_LEDGER.md` and `mk1/test/R4_ACCEPTANCE.md` close. Major remaining proof includes full regression, legacy-profile handling, complete Review package visibility, real-provider UAT, four-piece publishability UAT, exact-head pre-cert and exact-main post-cert.

## Candidate law

A candidate is an exact `developer` SHA, not another branch.

```text
developer@candidate SHA
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

Any tracked mutation after freeze supersedes the candidate. A failed SHA is immutable evidence and is never relabeled certified.

## Historical MK1 evidence

Earlier S0–S12/R2/R3 slice records remain valid historical evidence for the exact boundaries they certified. They do not supersede the current branch model or automatically certify R4.

## Build authorization

The phrase **“Take the hummer”** still means that the active design/architecture/plan graph is sufficiently closed to enter implementation. It never bypasses exact-SHA gates, product-quality UAT or post-merge certification.
