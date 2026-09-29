# R4 Execution Plan — Creative Production Closure

Status: **ACTIVE ON `developer`**

## Goal

Finish R4 without reopening already certified infrastructure unnecessarily. The work focuses on the creative/editorial/visual intelligence gap while preserving R2/R3 persistence, approval, recovery and exact-SHA laws.

## Phase A — Authority and profile quality

Close the input side before judging output quality.

- detect legacy malformed Profile topic/audience derivations;
- provide an explicit upgrade path to a new immutable ProfileVersion rather than rewriting history;
- freeze CreativeBrief provenance to the exact ProfileVersion and ContentPlan;
- make channel/format expectations explicit enough to avoid accidental text-only output when visual-first publishing is required.

Exit: one real test Profile can be inspected and its derived creative authority is understandable, bounded and versioned.

## Phase B — Editorial intelligence

Production candidate generation must use model-backed ideation constrained by Profile, goals, channel, memory and recent content. Deterministic services remain responsible for novelty, collisions, diversity and final plan freeze.

Required product behavior:

- requested batch cardinality is satisfied or fails explicitly;
- pieces are semantically distinct, not wording variants;
- no raw internal taxonomy or demo/test language;
- copy is useful enough that final human review is editing/approval, not rewriting from scratch;
- unsupported factual claims remain blocked by evidence rules.

## Phase C — Visual intelligence

A creative director layer chooses representation from the content need, not from a fixed vertical hardcode. Supported strategy may include typography/poster, diagram, infographic, composed UI/editorial layout, illustration or generated background imagery.

Generated imagery follows:

`VisualSpec requirement → provider → validated bytes → product AssetStore → SHA → resolved renderer input → Chromium composite → final owned asset`.

Provider output never becomes trusted by URL alone and must not invent authoritative editorial text inside the image.

## Phase D — QA and recovery

Editorial and visual QA are separate but both blocking.

Editorial QA: leakage, generic-template patterns, language, evidence, content density, progression, cross-piece collisions.

Visual QA: dimensions, text coverage, load/decode success, overflow, page completeness, duplicate pages, source-image digest binding and exact reconstruction.

Recovery must restart from persisted nodes and owned bytes; it must not silently call the image provider again to recreate an already frozen requirement.

## Phase E — Review package

Review must expose the actual publishable package:

- rendered creative or all carousel pages;
- title/hook;
- caption/body;
- CTA;
- hashtags when present;
- format/channel;
- QA verdict;
- progressive-disclosure lineage/evidence;
- exact revision identity.

Approval binds exactly what the reviewer saw.

## Phase F — Product UAT

Use at least one realistic Profile and request four pieces. The UAT is blocking unless:

- all four are present;
- all four are meaningfully distinct;
- profile/audience alignment is obvious;
- no demo/internal language is visible;
- visuals are coherent with copy;
- at least the required visual formats contain actual useful creatives;
- operator can plausibly publish after normal final review rather than reconstructing the content.

Record both successes and rejected outputs. A model/provider failure is evidence, not a reason to weaken the gate.

## Phase G — Certification

1. Close all R4 blockers or explicitly defer non-boundary items.
2. Run the machine-readable validation graph verifier.
3. Freeze one exact `developer` SHA in `CANDIDATE.md`.
4. Run all required exact-SHA CI/checks.
5. Attach product UAT evidence to that same SHA.
6. Reject candidate on any blocking failure.
7. Merge only a pre-certified exact head into `main`.
8. Re-run required gates against exact `main` merge SHA.
9. Seal documentation only after post-merge evidence exists.

## No-shortcut rules

No new branch is created to hide a red candidate. No failed SHA is force-moved or renamed into success. No demo output is accepted as proof of production creativity. No technical PASS substitutes for product publishability. No documentation claim may exceed demonstrated code/test evidence.
