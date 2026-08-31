# GROUNDING-01 — Evidence-first editorial trust contract

Status: IMPLEMENTED / CI CERTIFICATION PENDING

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

## Authority model

Grounding deliberately separates proposal from authority:

```text
AI / evaluator
    proposes claim -> evidence mapping
                |
                v
Deterministic GroundingPolicy
    validates mechanical policy
                |
                v
Human Grounding review
    VERIFIED / REJECTED
                |
                v
Approval boundary
```

A model cannot make its own assertion authoritative merely by labeling it `GROUNDED`.

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

A model may propose this classification. A deterministic policy checks whether the resulting assessment is mechanically eligible to proceed, and a human explicitly verifies the current assessment before approval.

### GroundingReviewSnapshot

The human verification record is bound to:

- exact final-content SHA-256,
- exact GroundingAssessment SHA-256,
- Grounding policy version,
- visible inference warnings,
- explicit human action timestamp.

Changing final content invalidates this review.

## Gate semantics

Allowed by deterministic policy:

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

A deterministic `PASS` is necessary but not sufficient for approval. The current assessment must also carry an explicit human `VERIFIED` Grounding review.

## Anti-loophole rules

Grounding only means something if the assessment is bound to the exact final-content bytes/revision. `GroundingAssessment.content_sha256` enforces this identity.

Implemented safeguards:

1. `grounding/evaluate` rejects an assessment whose `content_sha256` differs from the current `final_content`.
2. `SourcePacket.workspace_id` must equal the authoritative `ContentRun.workspace_id`.
3. A new evaluation clears any prior human Grounding review.
4. A content edit clears the assessment, gate and human review.
5. A human cannot mark a policy `BLOCK` assessment as `VERIFIED`.
6. Approval recomputes `GroundingPolicy` from the persisted SourcePacket + Assessment rather than trusting the stored gate snapshot.
7. Approval verifies that human review hashes still match the exact current content and assessment.
8. Approval freezes Grounding digests and policy version into the immutable approval bundle.
9. Existing optimistic concurrency prevents a review/edit/evaluation race from approving stale material.

This means direct tampering of the cached `grounding_gate` from `BLOCK` to `PASS` is not enough to cross the approval boundary.

## Writer contract

Generation should receive an explicit factual envelope:

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

## Implemented slices

### GROUNDING-01A — domain contracts

Implemented:

- `EvidenceRef`
- `SourcePacket`
- `Claim`
- `GroundingAssessment`
- `GroundingGateResult`
- `GroundingReviewSnapshot`

### GROUNDING-01B — deterministic policy

Implemented as `GroundingPolicy` with versioned, pure policy behavior that cannot be relaxed by model creativity.

### GROUNDING-01C — policy regression tests

Implemented golden policy cases for grounded facts, unsupported facts, contradictions, supported inference, unknown evidence references and incomplete extraction.

### GROUNDING-01E — ContentRun lifecycle integration

Implemented:

- source packet + assessment persisted on authoritative `ContentRun`,
- assessment bound to exact final-content SHA-256,
- workspace boundary enforced,
- edit invalidation,
- explicit human Grounding review,
- policy re-evaluation at approval time,
- `READY_FOR_REVIEW -> APPROVED` fail-closed unless current policy is `PASS` and review is `VERIFIED`,
- Grounding digests/policy version frozen into approval bundle,
- release E2E updated to use `edit -> evaluate -> verify -> approve`.

### GROUNDING-01P — lifecycle/adversarial tests

Implemented focused tests for:

- exact-revision persistence,
- stale assessment rejection,
- cross-workspace rejection,
- inspectable BLOCK result that cannot be verified,
- human review bound to exact hashes,
- stored-gate tampering that cannot bypass fresh policy evaluation.

## Next: GROUNDING-02 — semantic extraction and evidence matching

GROUNDING-01 establishes the authority boundary. It does **not** yet claim that prodAgentic can autonomously determine semantic truth reliably.

Next work:

- claim extractor with completeness contract,
- evidence matcher / entailment evaluation,
- contradiction detection,
- factual-envelope builder for Writer,
- explicit rewrite / soften protocol,
- Golden Content Set with real project evidence,
- local blind evaluation of faithfulness + editorial quality.

## Trust boundary

```text
Evidence
   |
   v
SourcePacket
   |
   v
Writer / Editor
   |
   v
Claim Extraction
   |
   v
Grounding evaluation
   |
   v
Deterministic GroundingPolicy
   |
   v
Human Grounding Review
   |
   v
Human Content Approval
   |
   v
Immutable Approval Bundle
   |
   v
Publisher
```

Grounding remains separate from Content Memory and publication authority. Content Memory may suggest evidence or similar content; it may never mark a claim true or authorize publication.
