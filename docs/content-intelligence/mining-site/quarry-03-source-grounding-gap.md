# Quarry 03 — Source Grounding Gap

## Question

Does the current generation pipeline durably know which sources support a run?

## OBSERVED

1. `PipelineOrchestrator` creates a `GenerationContext` containing:
   - run identity,
   - topic/style,
   - language resolution,
   - audience derived from profile,
   - content profile ID/snapshot.

2. The pipeline executes:

```text
idea -> ResearchAgent -> ContentWriter -> Editor -> VisualAgent
```

3. Research stage output is persisted as stage provenance.

4. Current `ContentRun` does not contain:
   - source IDs,
   - source-set digest,
   - grounding mode,
   - source authority,
   - source snapshot references.

5. Current approval bundle freezes final content + optional visual but no source-set identity.

6. The current research system prompt asks for practical information and avoidance of hallucinations, but no durable source contract is available to enforce/inspect that request.

## INFERRED

The current research stage provides generation provenance, not source provenance.

A model can produce useful research output without the product being able to answer:

- What deliberate source material was supplied?
- Which version/snapshot of that material was used?
- Was the run asked to be source-only?
- Did the source set change between generation and approval?

## PROPOSED

Introduce run-scoped source snapshots/references and a compact grounding snapshot.

Initial modes:

- `OPEN`
- `SOURCE_PREFERRED`
- `SOURCE_ONLY`

Initial source types should be deliberately narrow:

- pasted text,
- user assertion,
- repository/document excerpt already provided by an adapter,
- URL snapshot already provided by a safe adapter.

Do not build universal connector ingestion in this phase.

## Important trust distinction

A persisted source means:

> this material was deliberately available to the run.

It does NOT mean:

> every statement in this material is objectively verified truth.

The UI and docs must preserve this distinction.

## Approval implication

Proposed approval should freeze the `source_set_sha256` and grounding mode used for reviewed content.

This is run-level evidence, not claim-level citation.

## REJECTED

- Automatic continuous crawling of GitHub/Drive/Notion.
- Claim-level evidence graph in the first slice.
- Silent fallback from `SOURCE_ONLY` to model-general knowledge.
- Persisting connector tokens/cookies as source metadata.

## UNKNOWN

- Exact token/chunk budget for source selection requires implementation measurements.
- Which external source adapters should be productized first is a later market decision.

## Pre-build verdict

GAP CONFIRMED — stage provenance exists; deliberate source provenance does not.