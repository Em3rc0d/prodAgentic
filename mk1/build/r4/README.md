# MK1-R4 — Creative Production

Status: **DESIGN + IMPLEMENTATION HARDENING / NOT CERTIFIED**  
Active branch: `developer`  
Stable authority: `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e`  
R4 implementation ancestor: `7f0eac200c7c533cd8e09dd43a5a5546bcdad343`

## Purpose

R4 closes the gap between a technically valid content pipeline and a product that produces complete, profile-driven, publishable editorial packages with real visual production.

The release is not complete merely because services, persistence, rendering, QA, approval, or recovery are green. R4 is complete only when product-quality gates also prove that the resulting content is useful, distinct, visually coherent, free from internal/demo leakage, and suitable for final human review without reconstruction from scratch.

## Canonical R4 package

This directory is the release-local authority for R4:

- `ARCHITECTURE.md` — product/runtime architecture and validation graph.
- `BUILD_RECORD.md` — implementation truth and requirement-to-code traceability.
- `ERROR_LEDGER.md` — known failures, gaps, regressions and their dispositions.
- `CANDIDATE.md` — candidate freeze protocol and exact-SHA certification record.
- `../CERTIFICATION_GRAPH.json` — machine-readable reciprocal validation graph.
- `../../../scripts/verify_r4_cert_graph.py` — structural verifier for that graph.
- `../../test/R4_ACCEPTANCE.md` — product + technical acceptance gates.
- `../../mining-site/R4_RESEARCH_LEDGER.md` — provenance for external engineering guidance.

## Product contract

A normal production cycle must preserve this authority chain:

`ProfileVersion ↔ CreativeBrief ↔ CandidatePool ↔ ContentPlan ↔ ResearchPack ↔ ContentSpec ↔ EditorialGate ↔ VisualSpec ↔ SourceAsset ↔ RenderAsset ↔ VisualQA ↔ HumanReview ↔ ApprovalBundle ↔ Export/Publication ↔ Analytics/Learning ↔ EditorialMemory ↔ next CandidatePool`.

The graph is intentionally closed by the learning loop. No publication is treated as a terminal node and no new candidate pool is treated as an unexplained beginning.

## Non-negotiable R4 laws

1. `demo/simulation` and `production` are different product modes and must be visible as such.
2. Model output is proposal data, never authority by itself.
3. Profile, memory, novelty, evidence, content, visual and approval identities are immutable once frozen for a revision.
4. Generated source imagery must become product-owned bytes before rendering; remote mutable URLs are not authority.
5. Every owned artifact used for approval/export must have a digest and lineage.
6. Editorial quality and visual quality are release gates, not optional warnings.
7. Human approval binds the exact content revision, QA evidence and asset hashes.
8. Retry/recovery must reuse frozen authority rather than silently regenerate it.
9. A failed candidate SHA is immutable evidence and is never relabeled certified.
10. Promotion is always `developer exact SHA → pre-cert → main merge → exact-main post-cert`.

## Closure rule

R4 may be marked `CERTIFIED / CLOSED` only when every blocking node in `R4_ACCEPTANCE.md` has evidence, the graph verifier passes, the exact candidate SHA passes all required automated gates, a real-profile UAT meets publishability expectations, and the exact merged `main` SHA passes post-merge certification.
