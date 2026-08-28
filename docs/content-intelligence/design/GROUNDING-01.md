# GROUNDING-01 — Evidence-first editorial trust contract

Status: ACTIVE DESIGN / IMPLEMENTATION

## Governing principle

> **prodAgentic does not invent a better story. It finds the best story the evidence already contains.**

The Writer may improve expression. It may not improve reality.

This produces two complementary engines:

- **Value Engine** — find an angle worth reading.
- **Trust Engine** — ensure every factual increase in specificity is matched by evidence.

Attention without evidence is risk. Evidence without attention is documentation nobody reads. Attention plus evidence builds authority.

## Non-negotiable invariant

`GROUNDING-01`: **No unsupported factual claim may reach APPROVED.**

Claim-level provenance is therefore part of the Commercial V1 trust target. Earlier documentation that treated claim-level provenance as optional for the first release is superseded by this decision.

## Domain contracts

### EvidenceRef

An inspectable evidence item with:

- stable `evidence_id`,
- authority,
- source type,
- locator and/or excerpt and/or content hash,
- capture timestamp,
- optional metadata.

Evidence authority remains explicit:

- `USER_PROVIDED`
- `SOURCE_SNAPSHOT`
- `SYSTEM_DERIVED`
- `EXTERNAL_PUBLICATION_EVIDENCE`

### SourcePacket

The evidence boundary supplied to one grounded generation/evaluation context. It contains:

- workspace scope,
- evidence references,
- explicit allowed inferences,
- explicit prohibited claims,
- strict-mode policy.

A source packet is fuel for generation; it is not publication authority.

### Claim

Every meaningful statement extracted from final content is classified as one of:

- `FACT`
- `INFERENCE`
- `OPINION`
- `EXPERIENCE`
- `ESTIMATE`
- `PREDICTION`

and receives exactly one grounding state:

- `GROUNDED`
- `SUPPORTED_INFERENCE`
- `OPINION`
- `INSUFFICIENT_EVIDENCE`
- `CONTRADICTED`

A model may propose this classification. A deterministic policy decides whether the resulting assessment is eligible to proceed.

## Gate semantics

Allowed:

- `FACT` / `EXPERIENCE` -> `GROUNDED`
- `INFERENCE` / `ESTIMATE` / `PREDICTION` -> `SUPPORTED_INFERENCE`
- `OPINION` -> `OPINION`

Blocking:

- any `INSUFFICIENT_EVIDENCE`,
- any `CONTRADICTED`,
- evidence references outside the attached `SourcePacket`,
- incomplete claim extraction,
- an empty claim assessment in strict mode,
- semantic mismatches such as a fact being presented as a supported inference.

Supported inferences remain visible to human review even when the deterministic gate passes.

## Anti-loophole rule

Grounding only means something if the assessment is bound to the exact final-content bytes/revision. `GroundingAssessment.content_sha256` exists for this reason.

Any human or agent edit that changes final content must invalidate the prior grounding assessment before approval. A later implementation slice must enforce this at the `ContentRun` lifecycle boundary.

## Writer contract

Generation should eventually receive an explicit factual envelope:

```text
ALLOWED FACTS
- ...

ALLOWED INFERENCES
- ...

PROHIBITED / UNSUPPORTED CLAIMS
- ...
```

The Writer may:

- discover stronger structure,
- improve hooks,
- compress or expand explanations,
- increase clarity,
- improve rhythm and narrative order,
- make an existing implication explicit as an inference.

The Writer may not:

- manufacture metrics,
- increase severity,
- invent causality,
- invent customer impact,
- convert uncertainty into certainty,
- convert an inference into a fact,
- fabricate significance.

## Example

Evidence:

```text
150 tests passed.
2 tests failed.
Both failing tests instantiated PipelineOrchestrator(None).
Generation now fails closed without authoritative ContentRun persistence.
```

Allowed factual statement:

> Two legacy tests failed after the persistence hardening.

Allowed supported inference:

> The tests still represented an older lifecycle assumption.

Rejected:

> We almost shipped a catastrophic production incident.

Rejected:

> The new architecture improved reliability by 73%.

Neither rejected statement exists in the evidence.

## Implementation slices

### GROUNDING-01A — domain contracts

- `EvidenceRef`
- `SourcePacket`
- `Claim`
- `GroundingAssessment`
- `GroundingGateResult`

### GROUNDING-01B — deterministic policy

Pure policy code that cannot be relaxed by model creativity.

### GROUNDING-01C — regression tests

Golden policy cases for grounded facts, unsupported facts, contradictions, supported inference, unknown evidence references and incomplete extraction.

### GROUNDING-01E — ContentRun integration

Next:

- persist source packet and grounding assessment on the authoritative run,
- bind assessment to exact final-content SHA-256,
- invalidate grounding after edits,
- prevent `READY_FOR_REVIEW -> APPROVED` unless the exact current revision has `PASS`,
- freeze grounding evidence identifiers/digest into approval evidence.

### GROUNDING-02 — claim extraction and evaluation

Next after lifecycle integration:

- claim extractor,
- evidence matcher,
- contradiction detection,
- explicit rewrite/soften protocol,
- local golden dataset evaluation.

## Trust boundary

Grounding remains separate from Content Memory and from publication authority:

```text
Evidence -> SourcePacket -> Writer -> Claim Extraction -> Grounding Gate
                                                       |
                                                       v
                                                  Human Review
                                                       |
                                                       v
                                               Immutable Approval
                                                       |
                                                       v
                                                    Publisher
```

Content Memory may suggest evidence or similar content. It may never mark a claim true or authorize publication.
