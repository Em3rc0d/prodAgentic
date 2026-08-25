# Quarry 05 — Scale and Cost Boundary

## Question

Can the proposed Content Intelligence architecture remain reasonable at 100, 1000, or more users without one AI runtime per user?

## OBSERVED

1. Current backend is a shared FastAPI application.

2. Current generation agents are instantiated as service objects inside shared application code, not customer-dedicated processes.

3. Current Mongo persistence is collection-based and ContentRuns are documents.

4. Current visual service already bounds concurrent renders with a shared semaphore.

5. Current scheduler is a shared polling loop for explicitly scheduled publication work.

6. No current architecture requires one process/agent/model instance per user.

## INFERRED

The safest scaling direction is to preserve shared stateless/request-scoped execution and add workspace-scoped records.

The dangerous direction would be:

```text
user -> always-on personal agent -> continuous observation/learning
```

because costs and operational complexity grow with idle accounts rather than actual work.

## PROPOSED compute contract

The following actions may consume model/embedding/render compute:

- user asks for ideas/generation,
- final/idea representation needs first-time embedding,
- user/review flow requests overlap check,
- source-grounded generation resolves selected sources,
- visual intent/prompt/render is requested,
- explicit scheduled publication becomes due.

The following must consume zero content-intelligence model calls while idle:

- merely owning an account,
- merely having historical posts,
- merely having sources stored,
- merely having a ContentProfile.

## PROPOSED storage contract

Storage scales with durable content, not number of agents:

```text
workspaces
content_runs
content_memory
content_sources
```

No customer-dedicated database/vector service is required.

## Proposed 1000-workspace scenario

Illustrative, not benchmark evidence:

- 1000 workspaces,
- 100 historical memory items each,
- 100,000 compact memory records,
- shared API/worker pool,
- zero idle embedding calls.

100,000 records is a normal database-shape problem; 1000 persistent LLM agents would be a very different operational problem.

## Cost controls to implement/test

- embedding generated once per representation version,
- canonical hash check before semantic call where useful,
- bounded source token budget,
- bounded candidate result count,
- no unbounded provider retries,
- cache/reuse visual intent until source final content changes,
- no analytics polling in this program,
- no automatic background source crawling.

## Scale test metrics

Must measure, not assume:

- p50/p95/p99 memory-check latency,
- DB query count per check,
- embedding call count,
- memory footprint under concurrent requests,
- cross-workspace leakage (must be zero),
- degraded behavior under provider limit/timeouts.

## REJECTED

- Per-user daemon.
- Per-user vector database.
- Per-user model process.
- Continuous inference to update a personality profile.
- Realtime analytics polling for all users.

## UNKNOWN

- Exact point at which native vector indexing becomes necessary.
- Exact worker pool sizing for real traffic.
- Real provider rate limits/cost profile under customer usage.

These are deployment measurements, not reasons to introduce persistent user agents preemptively.

## Pre-build verdict

ARCHITECTURE DIRECTION ACCEPTED; SCALE PERFORMANCE NOT YET PROVEN.