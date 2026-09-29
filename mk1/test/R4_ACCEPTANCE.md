# R4 Acceptance & Certification Matrix

Status: **OPEN / BLOCKING**

R4 certification requires both system integrity and product quality. Passing one column cannot compensate for failing the other.

## Gate matrix

| Gate | Must prove | Evidence class | Blocking |
|---|---|---|---|
| A1 Profile authority | exact immutable ProfileVersion used by planning | unit/integration + UAT receipt | YES |
| A2 Legacy profile handling | malformed historical profile data is detected/upgraded without silent rewrite | regression + migration/UAT | YES |
| B1 Batch completeness | requested count is produced or explicit failure returned | integration/browser | YES |
| B2 Semantic distinctness | pieces are not topic/hook/structure paraphrases | novelty regression + UAT | YES |
| B3 Profile alignment | audience/goals/voice/channel influence output | golden/UAT | YES |
| B4 Internal leakage | no demo, schema, workflow or control-state language reaches publishable output | negative regression | YES |
| B5 Editorial quality | generic/template/low-value output cannot pass production gate | golden set + UAT | YES |
| B6 Evidence integrity | factual claims respect evidence/claim policy | unit/integration | YES |
| C1 Visual strategy | format/visual choice has typed authority in VisualSpec | unit/integration | YES |
| C2 Generated source ownership | provider bytes become owned asset with MIME/magic/size checks and SHA | fake-provider + integration | YES |
| C3 No mutable remote authority | renderer/approval cannot depend on mutable remote image URL | negative regression | YES |
| C4 Image idempotency | retry/restart reuses exact source asset for frozen requirement | restart/recovery | YES |
| C5 Render copy integrity | rendered editorial copy references exact ContentSpec | renderer tests | YES |
| D1 Visual QA | dimensions/load/overflow/page/duplicate/source-lineage checks pass | QA suite | YES |
| D2 QA reconstruction | QA rebuilds exact render inputs without provider regeneration | restart/recovery | YES |
| E1 Review completeness | visual + title/hook + caption/body + CTA + hashtags + QA/revision are visible | browser desktop/mobile | YES |
| E2 Exact approval | approval freezes exact revision, QA evidence and owned hashes | approval regression | YES |
| F1 Persistence | approved/reviewable data and assets survive backend restart | recovery journey | YES |
| F2 Export integrity | exported package is derived from approved authority | integration/browser | YES |
| F3 Learning loop | outcome/memory can influence later planning without mutating historical authority | integration | YES |
| G1 Mode truth | simulation and production are visibly and behaviorally distinct | UI + backend regression | YES |
| G2 Real provider | bounded real model/image provider path succeeds for a real Profile | live UAT | YES |
| G3 Product publishability | reviewer judges package ready for ordinary final review, not reconstruction | signed UAT receipt | YES |
| H1 Full regression | previous certified R2/R3 invariants remain green | historical matrix | YES |
| H2 Graph verifier | certification graph has no orphan/dangling/non-reciprocal node | script/CI | YES |
| H3 Exact-head pre-cert | all required checks bind exact candidate SHA | CI receipt | YES |
| H4 Exact-main post-cert | required checks bind exact merged main SHA | CI receipt | YES |

## Product UAT rubric

For the four-piece real-profile batch, score each piece across relevance, novelty, specificity/value, voice fit, visual-copy coherence and publishability. Any visible internal/demo language is an automatic rejection. Any piece requiring a complete editorial rewrite is rejected. Any visual that is merely a placeholder, malformed, misleading relative to the copy, or structurally unusable is rejected.

The acceptance decision is not “the model is creative.” The decision is whether the system produced a bounded, traceable package that a human account owner can reasonably approve/edit/publish.

## Carousel-specific acceptance

- page count matches the frozen ContentSpec/VisualSpec structure;
- every page is reachable in Review;
- critical copy coverage is exact;
- no duplicate semantic pages unless explicitly intentional;
- page ordering remains stable across restart/recovery;
- all page assets are owned and hash-bound.

## Failure policy

Any blocking failure rejects the candidate SHA. Fixes happen on `developer`, then a new SHA is frozen. Waivers are not allowed for product-quality blockers; a requirement may only be deferred when it is explicitly outside the declared R4 product boundary and documentation/product claims are reduced accordingly.
