# Quarry 02 — Content Memory Gap

## Question

What duplicate protection exists today, and what does not?

## OBSERVED

1. Current publication idempotency protects the same `ContentRun` / same immutable approval bundle:
   - if the run is already `PUBLISHED`,
   - publication evidence status is `PUBLISHED`,
   - and stored `bundle_sha256` matches current approval bundle,
   - `PublicationCoordinator` returns existing evidence instead of making another external post.

2. Current atomic claim also prevents two workers from publishing the same schedulable run concurrently.

3. There is no repository/service named for embeddings, vector search, semantic similarity, or content-memory overlap in the current tree.

4. Current `ContentRun` has no `memory_check` snapshot.

5. Current `posts` projection includes content and zeroed performance fields, but no durable semantic representation or duplicate relationship.

## INFERRED

Existing protection solves:

- replay of the same approved run,
- concurrent worker duplication of the same run.

It does NOT solve:

- user creates a new run with copied final content,
- user paraphrases an already-published idea,
- new idea is semantically the same lesson with different wording,
- identifying a useful previous related post during review.

## PROPOSED

Introduce two layers:

### Layer A — deterministic exact/normalized identity

Always available, model-independent.

- canonicalize text,
- version canonicalizer,
- store normalized SHA-256,
- use as a hard duplicate signal within a workspace.

### Layer B — semantic similarity

Optional provider-backed embeddings.

- workspace scoped,
- generated on content representation creation/change,
- reused on later checks,
- degrade explicitly when unavailable.

## Product distinction

Exact duplicate may block publication.
Semantic high-overlap initially warns; it does not automatically rewrite/delete.

This protects against false positives while still surfacing repetition.

## REJECTED

- A vector database per user.
- Re-embedding the entire history on every generation.
- Treating provider outage as `NO_OVERLAP`.
- Cross-workspace similarity.

## UNKNOWN

- Best semantic model/provider and thresholds are not yet proven.
- Native Mongo vector capability vs application-side bounded cosine similarity requires scale evidence.

## Required evidence before semantic release

- Golden Dataset precision/recall for duplicate vs new-angle cases.
- Provider failure behavior.
- 1000-workspace isolation/bounded-query test.
- Proof exact duplicate prevention still works with semantic provider disabled.

## Pre-build verdict

GAP CONFIRMED — exact run idempotency exists; cross-run content memory does not.