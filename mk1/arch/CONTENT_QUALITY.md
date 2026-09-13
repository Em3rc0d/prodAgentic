# MK1-R3 — Profile-driven Content Quality Architecture

Status: IMPLEMENTED / CERTIFICATION OPEN

## Product invariant

prodAgentic must not optimize for one editorial account, industry or creator. The same machinery must be able to serve a developer, automotive educator, consultant, restaurant, professional practice, business, student creator or personal brand without vertical-specific branches in the production core.

Content Seller is a quality benchmark, not a hardcoded product mode.

## Boundary

R2 remains sealed at `main@6b6a73c554eab4926800c5c24df887c70aa678cc`. R3 starts from that exact commit and changes only a new candidate branch. All R2 authority, digest, persistence, rendering, QA, approval, recovery and export invariants remain required.

## R3 flow

```text
Accepted ProfileVersion
        |
        v
Profile-derived Creative Brief
        |
        +--> compact topic families / novelty planning
        |
        v
ResearchPackV1
        |
        v
Writer -> ContentSpecV1
        |
        v
Editor / Publishability Gate
        |  \__ deterministic floor: internal leakage / structural anti-slop
        v
Frozen ContentRevisionV1
        |
        v
DesignProfileV1 + semantic VisualSpec
        |
        v
Existing deterministic Renderer
        |
        v
Existing technical / visual QA
        |
        v
Human Review -> Approval -> Manual Export
```

## Specialization law

Client-specific behavior may come from frozen authority only:

- identity and account type;
- audience;
- goals;
- editorial topic families and novelty memory;
- voice and copy policy;
- visual traits;
- publishing channels;
- the selected plan/role/angle/format;
- trusted evidence in ResearchPack.

The production core must not contain rules such as `if automotive`, `if lawyer`, `if Content Seller`, or equivalent vertical routing.

## Creative Brief

`application/content_quality/brief.py` creates deterministic editorial guidance from Profile + Plan. It describes audience, desired effect, role, voice, channel expectations and a common quality bar. It is a derived view, not new authority, and therefore does not add another user form.

## Publishability floor

Model judgment alone is insufficient. `application/content_quality/policy.py` independently blocks audience-facing artifacts that leak prodAgentic internals or violate structural invariants. Examples include demo/test narration, workflow states, schema/control identifiers, internal target tokens and duplicate carousel headlines.

The policy deliberately does **not** reject arbitrary technical syntax. A software client may legitimately publish identifiers such as `user_id` or `retry_count`; only prodAgentic-owned control vocabulary is fail-closed.

Soft editorial risks such as generic hooks, low value density, engagement-bait CTAs or underused formats remain warnings for the Editor/human reviewer unless they cross a deterministic invariant.

## Profile setup without form inflation

R3 preserves the simple Profile UX. Topic families are conservatively derived from explicit audience text when no example hashtags exist. Visual traits are derived only from explicit voice choices through an allowlist. Unknown values never gain renderer authority.

No additional mandatory brand questionnaire is introduced.

## Visual direction

VisualSpec stays typed and copy-referential. R3 adds semantic patterns, role-sensitive layout choice, bounded icon/divider accents and diagrams for multi-step/relationship information while keeping generated/external-image strategies outside the certified deterministic renderer boundary.

Visual archetypes come from traits such as sparse/dense/bold/dark/soft rather than business verticals. Existing renderer token vocabulary remains closed.

## Non-goals for R3

- no autonomous external image sourcing;
- no fabricated evidence, metrics or personal experience;
- no claim that automated quality replaces human review;
- no LinkedIn/live-provider publication certification;
- no vertical-specific template library;
- no mutation of rejected or sealed R2 evidence.

## Certification law

A candidate is acceptable only if its exact head passes the full applicable workflow/check matrix and the product journey demonstrates that publishability improvements do not weaken R2 authority. Any tracked mutation creates a new candidate head. Merge is followed by exact-main post-merge recertification before R3 can be marked CERTIFIED/CLOSED.
