# MK1-R3 Acceptance — Publishable Content Quality

Status: OPEN

## Required automated gates

- existing frontend unit/build gate;
- existing backend full test suite;
- existing browser certification;
- existing Docker/local-release gate;
- existing Phase H and S3-S12 workflow gates;
- R3 content-quality regressions.

## R3-specific acceptance matrix

| Gate | Required result |
| --- | --- |
| Cross-client Profile derivation | PASS — no vertical routing, compact topics from explicit setup |
| Creative Brief | PASS — frozen Profile + Plan only |
| Internal leakage | PASS — test/schema/workflow/control vocabulary blocked |
| Technical syntax | PASS — legitimate code identifiers do not false-block |
| Editorial approval authority | PASS — model approval cannot bypass deterministic blockers |
| Demo fixture | PASS — audience-facing output for all four formats |
| Carousel semantics | PASS — pages progress by role; no duplicate headline approval |
| Infographic semantics | PASS — multiple information groups / relationships remain copy-bound |
| VisualSpec lineage | PASS — existing exact-copy coverage and tamper tests stay green |
| Renderer geometry | PASS — no clipping/overflow regression |
| R2 journey | PASS — Profile → Batch → Produce → Render → QA → Review → Approval → Export + recovery |

## Manual acceptance question

For each sampled Profile, the reviewer must be able to answer **yes** to:

> Would I hand this candidate to the account owner for final review without first explaining that it is a demo, cleaning internal system language, or rebuilding the content structure from scratch?

This is not permission to auto-publish. Human review remains authoritative.

## Cross-client sample set

Certification should exercise at least these *archetypes*, not hardcoded product modes:

- education / technical voice;
- business / direct or bold voice;
- personal brand / friendly or soft voice.

The implementation must pass through the same Profile → Plan → Production → Visual → QA pipeline for all samples.

## Evidence rule

Do not mark this document closed from a local observation alone. The accepted candidate must be tied to an exact commit SHA and all required GitHub checks. After merge, repeat the required matrix on the exact merged `main` SHA.
