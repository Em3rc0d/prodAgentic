# prodAgentic MK1 Status

**As of:** 2026-09-28  
**Stable authority:** `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e` — MK1-R3 certified  
**Integration baseline:** `developer@61bf7f93b37b00f3315c3f710d8005fed977e672` — intentionally untouched during independent R4.1 audit  
**Active certification line:** PR #69 / exact head SHA on `r4.1-reliability-evidence-authority`  
**R4 state:** PRE-UAT HARDENING / NOT CERTIFIED

## Canonical authority model

```text
main
  └─ stable/certified authority only

developer
  └─ integration authority

PR #69 exact head SHA
  └─ temporary R4.1 certification candidate only
```

A branch name is never a release identity. The exact PR head SHA plus its workflow receipts is the pre-UAT candidate. The temporary R4.1 branch exists only to preserve `main` and `developer` while the independent audit is completed; after R4 closure, ordinary work returns to the two-branch model.

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

## R4 implemented and automated

The current R4.1 line includes:

- model-backed 12-candidate planning with application-owned cardinality;
- memory/novelty/diversity selection;
- governed auto-format policy for visual-first Profile/channel authority;
- conditional legacy Profile upgrade path that creates an immutable next version while preserving history;
- evidence-grounded Research, Writer and Editor contracts;
- factual-modality blockers;
- product-owned generated/source asset bytes and digest lineage;
- deterministic visual fallback when an optional generated-image enhancement is unavailable;
- Chromium rendering + geometry QA + restart reconstruction;
- bounded production recovery and replacement authority;
- immutable approval package and verified manual export;
- exact-SHA historical, Redis, browser, renderer and Docker regression gates.

These are implemented capabilities, not a certification claim.

## Remaining R4 closure gates

R4 remains open until the exact current PR head proves all of the following:

1. canonical 9-workflow exact-SHA matrix green;
2. locked Python dependencies pass `pip-audit`;
3. frontend dependency graph passes `npm audit --audit-level=high`;
4. local production/non-demo runtime is rebuilt from that exact SHA;
5. the selected real Profile authority is inspected: eligible malformed legacy authority requires an explicit human upgrade decision, while a clean Profile records `NO_UPGRADE_REQUIRED`;
6. the exact current ProfileVersion and digest are frozen and one fresh real-provider ×4 reaches **4/4 Reviewable**;
7. human review gives PASS to all four exact final packages;
8. repository branch protection / required-check rules are enabled before promotion;
9. merge is explicitly authorized;
10. exact merged `main` SHA passes post-certification and receives a release receipt.

For the currently inspected Em3rc0d authority, the read-only diagnostic found clean `USER_ACCEPTED` Profile v1 with digest `6c24104a9df55df10c55dd1affb6d28672139ca7ff3da0ba2c3ee90348f45c20`, no malformed topic family and no matching legacy `content_profile`; its current certification disposition is `NO_UPGRADE_REQUIRED`.

Any tracked change or product defect creates a new candidate SHA. A failed SHA remains failed historical evidence.

## Historical MK1 evidence

Earlier S0–S12/R2/R3 slice records remain valid historical evidence for the exact boundaries they certified. They do not automatically certify R4.

## Build authorization

The phrase **“Take the hummer”** means the active design/architecture/plan graph is sufficiently closed to enter implementation. It never bypasses exact-SHA gates, product-quality UAT, human approval or post-merge certification.
