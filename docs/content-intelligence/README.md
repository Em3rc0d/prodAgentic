# prodAgentic Content Intelligence Program

Status: DOCUMENTATION GATE
Branch: `feat/content-intelligence-foundation`
Base: `feat/release-e2e-certification`

## Purpose

Turn prodAgentic from a strong content generation and publication workflow into a differentiated content production system without introducing a persistent per-user AI brain, always-on agents, or infrastructure that becomes expensive at 100-1000+ users.

The governing product principle is:

> prodAgentic should remember content, not simulate a person.

The governing engineering principle is:

> Compute on demand, persist durable evidence, remain almost idle when the user is idle.

## Current foundation we are preserving

The existing release branch already owns these trusted capabilities and they are NOT to be rewritten by this program:

- `ContentRun` as the authoritative generation aggregate.
- Versioned `ContentProfile` snapshots attached to runs.
- Stage lineage for research, write, edit, and visual prompt generation.
- Human review and immutable approval bundles.
- Owned visual artifacts with byte SHA-256 evidence.
- One `PublicationCoordinator` shared by manual and scheduled publishing.
- Atomic state claims around `APPROVED -> PUBLISHING -> PUBLISHED` and `SCHEDULED -> PUBLISHING -> PUBLISHED`.
- Durable scheduling with multi-instance safety.
- Publication evidence including provider identity and external post/image URNs.
- Product-boundary idempotency for already published approved bundles.
- Backend and frontend release-focused automated tests.

## Problem to solve

A user can still reasonably ask: "Why not just use a general chat model to write this post?"

This program answers with capabilities a stateless chat window does not naturally own:

1. **Content Memory** — know what has already been created and published, including near-duplicate ideas.
2. **Source Grounding** — bind a run to explicit sources and make source use inspectable.
3. **Visual Intelligence** — choose the correct communicative visual form before generating a render prompt.
4. **Reliable Distribution** — continue using the existing approval, scheduling, publication and evidence contracts.

## Explicit non-goals

The following are rejected for this program unless future measured evidence reopens them:

- Persistent per-user AI processes.
- A continuously learning personal "brain".
- Background crawling of every connected source.
- Automatic mutation of user identity, expertise or voice from observed behavior.
- A knowledge graph covering all user activity.
- Realtime analytics polling.
- Multi-network publishing expansion before LinkedIn is proven in production.
- Replacing MongoDB with a new database only to support one feature.
- Running a dedicated vector service per customer.
- Building a Canva-like visual editor.
- Building a CRM.

## Execution order

The program is intentionally staged:

1. `brainstorming/` — hypotheses, alternatives, rejected ideas, value/risk analysis.
2. `design/` — user-facing behavior and product contracts.
3. `architecture/` — data, services, isolation, scaling and failure contracts.
4. `build/` — incremental implementation slices and migration rules.
5. `test/` — automated, integration, scale and release gates.
6. `mining-site/` — evidence gathered from the existing repository and experiments. Every quarry must distinguish OBSERVED from PROPOSED.
7. `golden-dataset/` — deterministic cases used to prevent regressions in memory, grounding and visual-intent decisions.
8. Only after the documentation gate is internally coherent do code changes begin.

## Priority sequence

### CI-01 — Semantic Content Memory

Goal: before publication, detect whether the same or substantially overlapping idea already exists in the workspace history.

Initial product behavior:

- Exact duplicate: BLOCK publication unless explicitly reconciled as the already-published record.
- Strong semantic overlap: WARN and show the closest previous content.
- Moderate overlap: informative signal only.
- Distinct content: no interruption.

This system is workspace-scoped and on-demand. It is not a user personality model.

### CI-02 — Source-Grounded ContentRuns

Goal: a run may carry explicit source snapshots/references used during generation.

Initial source types:

- pasted note/text,
- URL metadata/text snapshot when supplied by an integration,
- document/repository excerpt supplied by an integration,
- explicit user assertions.

The first release does NOT require claim-level provenance. It requires run-level source traceability and a strict mode that can instruct generation to use only attached sources.

### CI-03 — Visual Intelligence

Goal: decide what visual form communicates the post before generating an image prompt.

Initial intent classes:

- `TECHNICAL_DIAGRAM`
- `TECHNICAL_ILLUSTRATION`
- `DATA_VISUALIZATION`
- `BEFORE_AFTER`
- `PRODUCT_HERO`
- `EDITORIAL`
- `CINEMATIC_METAPHOR`
- `NO_VISUAL`

The existing render service remains the rendering boundary. Visual Intelligence produces an inspectable intent and prompt strategy; it does not replace rendering.

### CI-04 — Lightweight Voice Profile

Deferred until CI-01 through CI-03 are proven. If implemented, it remains a compact explicit profile or one-time imported-post analysis. No continuous invisible learning.

### CI-05 — Opportunity Mining

Deferred. Must be on-demand. A user chooses a source and asks prodAgentic to find content opportunities; no continuous background scanning.

## Scalability contract

For 1, 100, 1000, or more users, the architecture should follow the same shape:

- shared API instances,
- shared worker pools,
- workspace-scoped persisted records,
- jobs only when requested or when an explicit schedule becomes due,
- no user-dedicated daemon,
- no customer-dedicated model instance,
- no customer-dedicated vector database.

A feature is rejected or redesigned if its normal operation requires substantial compute while the relevant user/workspace is idle.

## Trust contract

prodAgentic may infer a recommendation during a request, but persisted facts must have a clear authority:

- `USER_PROVIDED`
- `SOURCE_SNAPSHOT`
- `SYSTEM_DERIVED`
- `EXTERNAL_PUBLICATION_EVIDENCE`

Important identity/expertise claims are never silently converted from inference into user truth.

## Documentation gate exit criteria

Construction may begin only when all of the following are documented:

- Product behavior for CI-01, CI-02 and CI-03.
- Data ownership and lifecycle additions to `ContentRun`.
- Workspace isolation contract.
- Failure behavior and fallback behavior.
- Cost/compute boundary at 1000 users.
- Golden dataset format and minimum cases.
- Test gates proving no regression to approval/publishing/scheduling.
- Explicit statement of what is NOT being built.

## Release sequencing

This branch does not supersede the existing external release gate. Real LinkedIn publication proof remains a separate prerequisite for calling the current publishing layer production-certified.

Content Intelligence is layered on top of that trusted lifecycle; it must never weaken publication idempotency, approval immutability, or publication evidence.