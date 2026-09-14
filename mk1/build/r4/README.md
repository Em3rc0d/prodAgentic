# MK1-R4 — Creative Production

Status: **DESIGN + IMPLEMENTATION HARDENING / NOT CERTIFIED**  
Active branch: `developer`  
Stable authority: `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e`  
R4 implementation ancestor: `7f0eac200c7c533cd8e09dd43a5a5546bcdad343`

## Purpose

R4 closes the gap between a technically valid content pipeline and a product that produces complete, profile-driven, publishable editorial packages with real visual production.

The release is not complete merely because services, persistence, rendering, QA, approval, or recovery are green. R4 is complete only when product-quality gates also prove that the resulting content is useful, distinct, visually coherent, free from internal/demo leakage, and suitable for final human review without reconstruction from scratch.

## Canonical R4 package

R4 is intentionally distributed across the standard MK1 evidence structure while remaining one linked authority graph:

- `mk1/brainstorming/R4_CREATIVE_PRODUCTION_THESIS.md` — product thesis and failure definition.
- `mk1/design/R4_CREATIVE_PRODUCTION.md` — user-facing product/UX contract.
- `mk1/arch/R4_CONTRACTS.md` — typed cross-layer contracts and invariants.
- `mk1/arch/R4_SECURITY.md` — trust zones, threat model and security boundaries.
- `mk1/build/r4/ARCHITECTURE.md` — runtime architecture and reciprocal validation graph.
- `mk1/build/r4/BUILD_RECORD.md` — implementation truth and requirement-to-code traceability.
- `mk1/build/r4/ERROR_LEDGER.md` — known failures, gaps, regressions and dispositions.
- `mk1/build/r4/CANDIDATE.md` — exact-SHA candidate/release protocol.
- `mk1/build/r4/CERTIFICATION_GRAPH.json` — machine-readable reciprocal validation graph.
- `mk1/plan/R4_EXECUTION_PLAN.md` — remaining closure/build/certification plan.
- `mk1/test/R4_ACCEPTANCE.md` — product + technical acceptance gates.
- `mk1/mining-site/R4_RESEARCH_LEDGER.md` — provenance for external engineering guidance.
- `mk1/quarries/R4_LEARNING_AND_PROFILE_AUTHORITY.md` — learning-loop/profile-authority design finding.
- `scripts/verify_r4_cert_graph.py` — structural graph verifier.

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

## Graph verification

Structural development check:

```bash
python scripts/verify_r4_cert_graph.py
```

Frozen candidate/release mode additionally requires digests:

```bash
python scripts/verify_r4_cert_graph.py --require-digests
```

The verifier proves graph structure only. It does not replace editorial/visual UAT, exact-SHA CI, provider testing, supply-chain verification or human review.

## Closure rule

R4 may be marked `CERTIFIED / CLOSED` only when every blocking node in `mk1/test/R4_ACCEPTANCE.md` has evidence, the graph verifier passes, the exact candidate SHA passes all required automated gates, a real-profile UAT meets publishability expectations, and the exact merged `main` SHA passes post-merge certification.
