# GROUNDING-02 — Semantic proposal layer

Status: ACTIVE IMPLEMENTATION

## Purpose

GROUNDING-01 established the lifecycle authority boundary:

> no unsupported factual claim may reach `APPROVED`.

GROUNDING-02 introduces the semantic layer that helps build the claim-to-evidence map without granting the semantic model authority over truth.

## Trust invariant

A claim extractor or evidence matcher is a **proposal system**, not an authority system.

It may propose:

- what statements in final content are claims;
- what semantic type each claim appears to have;
- what evidence appears to support or contradict a claim;
- confidence and rationale for those proposals.

It may **not** assign:

- `GROUNDED`;
- `SUPPORTED_INFERENCE`;
- `INSUFFICIENT_EVIDENCE`;
- `CONTRADICTED`;
- `PASS` / `BLOCK`;
- human verification;
- publication approval.

Those decisions belong to later deterministic or human authority layers.

## GROUNDING-02A — proposal-to-assessment boundary

Implemented contracts:

### ClaimProposal

Non-authoritative extraction result:

- `claim_id`
- `statement`
- proposed `claim_type`
- confidence
- optional exact text span (`text_start`, `text_end`)

There is intentionally no `grounding_status` field.

### EvidenceMatchProposal

Non-authoritative relation proposal:

- `claim_id`
- `evidence_id`
- relation:
  - `SUPPORTS`
  - `CONTRADICTS`
  - `INSUFFICIENT`
- confidence
- rationale

### GroundingEvaluationDraft

Proposal envelope bound to:

- one `SourcePacket` identity;
- one exact final-content SHA-256;
- one evaluator version;
- an explicit extraction completeness flag.

The draft rejects:

- duplicate claim ids;
- matches to claims that were never extracted;
- duplicate identical claim/evidence/relation tuples;
- malformed content digests.

### GroundingAssessmentBuilder

Deterministic conversion from proposals to authoritative assessment state.

Precedence is deliberately conservative:

```text
CONTRADICTS
    ↓
CONTRADICTED

(no contradiction) + SUPPORTS
    ↓
FACT / EXPERIENCE -> GROUNDED
INFERENCE / ESTIMATE / PREDICTION -> SUPPORTED_INFERENCE

(no contradiction) + (no support)
    ↓
INSUFFICIENT_EVIDENCE
```

Contradiction is not averaged away by supporting evidence.

Opinions remain `OPINION` and do not borrow factual authority from evidence links.

Unknown evidence ids are not silently discarded. If a proposal claims support from evidence outside the packet, the resulting assessment retains that reference so `GroundingPolicy` can fail closed.

## Authority chain

```text
Final Content
    ↓
Claim Extractor
    ↓ proposal
ClaimProposal[]
    ↓
Evidence Matcher
    ↓ proposal
EvidenceMatchProposal[]
    ↓
GroundingEvaluationDraft
    ↓ deterministic derivation
GroundingAssessmentBuilder
    ↓
GroundingAssessment
    ↓ deterministic policy
GroundingPolicy
    ↓
PASS / BLOCK
    ↓
Human Grounding Review
    ↓
VERIFIED / REJECTED
    ↓
Human Content Approval
```

No earlier layer may impersonate a later authority layer.

## Why this separation matters

Without this boundary, a single model response could effectively say:

```text
I extracted this claim.
I found evidence for it.
Therefore I declare it GROUNDED.
```

That collapses proposal, adjudication and authority into one probabilistic component.

GROUNDING-02A instead allows the semantic evaluator to be replaced, benchmarked or challenged without changing the mechanical trust contract.

## Current limitations

GROUNDING-02A does **not** yet provide a production semantic extractor or entailment model. It provides the safe data model and deterministic conversion contract those components must satisfy.

The human remains the final verifier of the claim-to-evidence map in Commercial V1.

## Next slices

### GROUNDING-02B — deterministic factual envelope

Derive a Writer-facing envelope from verified evidence/assessment state:

```text
ALLOWED FACTS
ALLOWED INFERENCES
PROHIBITED / UNSUPPORTED CLAIMS
```

### GROUNDING-02C — semantic extractor/matcher adapter

- structured claim extraction;
- evidence candidate selection;
- support / contradiction proposals;
- completeness signal;
- provider/model provenance.

### GROUNDING-02D — soften/remove protocol

For blocked claims:

```text
unsupported claim
    ↓
can weaker wording be supported?
    ├─ yes -> SOFTEN
    └─ no  -> REMOVE
```

### GROUNDING-02E — Golden Content Set

Benchmark semantic fidelity and editorial usefulness using real prodAgentic project evidence, known allowed facts, known forbidden claims and strong supported angles.
