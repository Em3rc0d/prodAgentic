# MK1 Decision Closure

Status: **CLOSED FOR DESIGN FREEZE**

This document records the major questions that had to stop being ambiguous before implementation could start.

## Closed decisions

1. **Product identity** — governed content operating system, not prompt chain or generic workflow builder.
2. **Primary UX** — Home, Profiles, Create, Review, Calendar, Analytics with progressive disclosure.
3. **Domain root** — Tenant scope containing Profiles and execution/evidence entities.
4. **Content separation** — Batch, ContentItem and GenerationRun are distinct concepts.
5. **Memory authority** — recent editorial memory includes approved/scheduled/published work and sufficiently advanced pending work according to policy.
6. **Novelty** — multi-layer evaluation using canonical taxonomy, aliases, semantic similarity, angle, creative pattern and current-batch comparison.
7. **Planner** — generates an oversized candidate pool, evaluates it, then selects a balanced batch.
8. **Agent cell** — Planner, Research, Writer, Editor, Visual; deterministic services remain services rather than agents.
9. **Agent transport** — versioned Pydantic contracts.
10. **Visual architecture** — `VisualSpecV1` is the intermediate representation; critical editorial text is composed deterministically.
11. **Renderer V1** — HTML/SVG/CSS composition rendered through Chromium/Playwright behind a renderer port; generated imagery is a component, not the authority for critical text.
12. **QA** — deterministic + semantic + visual stages with bounded automatic recovery.
13. **Approval** — explicit human approval in V1, immutable bundle, digest-bound assets.
14. **Storage** — MongoDB system of record; `AssetStore` port with durable filesystem first.
15. **Queue** — Redis Streams + consumer groups for transport; Mongo domain state remains authoritative.
16. **Scheduling** — schedules persist in Mongo; dispatcher publishes recoverable job envelopes to Redis.
17. **Publication semantics** — at-least-once transport, atomic domain claim, idempotency, receipt and reconciliation; never claim distributed exactly-once.
18. **Automatic platforms V1** — LinkedIn first; unsupported channels receive a manual publish package.
19. **Analytics** — timestamped snapshots plus summarized features; raw metrics do not go directly into creative prompts.
20. **Tenancy** — all new MK1 domain entities are tenant-scoped; first deployment may bootstrap a single tenant.
21. **Architecture shape** — modular monolith plus separately runnable workers; no microservice split until measured boundaries justify it.
22. **Implementation method** — evidence-driven design freeze, contract-first work, certified vertical slices.

## Deliberately deferred but non-blocking

The following are implementation calibrations or later-scope investigations, not reasons to delay Slice 1:

- exact novelty thresholds per Profile category;
- Instagram/TikTok automatic-publishing capability contracts;
- GIF/short-video renderer;
- autonomous approval policies;
- advanced learning/optimization;
- object-store provider selection for hosted scale.

They live in `quarries/` until promoted.
