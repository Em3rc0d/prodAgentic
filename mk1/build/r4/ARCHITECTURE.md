# R4 Architecture — Reciprocal Validation Graph

Status: **AUTHORITATIVE DESIGN / IMPLEMENTATION HARDENING**

## 1. Architectural goal

prodAgentic is a governed content-production system, not a prompt wrapper. R4 must transform profile authority into a complete editorial package while preserving traceability, reproducibility where required, human authority, and recovery after partial failure.

The architecture is modeled as a **reciprocal validation graph**. “Blockchain-like” here means tamper-evident identity, immutable receipts, predecessor/successor validation, append-only evidence and explicit state transitions; it does **not** mean cryptocurrency, consensus mining, or pretending a database is a public blockchain.

## 2. Closed operational graph

```text
Analytics / outcomes
       ↓
LearningProposal
       ↓
Human profile decision
       ↓
ProfileVersion ───────────────┐
       ↓                      │
CreativeBrief                │
       ↓                      │
CandidatePool ← EditorialMemory
       ↓                 ↑
Novelty / diversity      │
       ↓                 │
ContentPlan              │
       ↓                 │
ResearchPack             │
       ↓                 │
ContentSpec              │
       ↓                 │
EditorialGate            │
       ↓                 │
VisualSpec               │
       ↓                 │
SourceAsset(s)           │
       ↓                 │
RenderAsset(s)           │
       ↓                 │
VisualQA                 │
       ↓                 │
HumanReview              │
       ↓                 │
ApprovalBundle           │
       ↓                 │
Export / Publication     │
       ↓                 │
Analytics / outcomes ────┘
```

Every runtime node must be addressable by stable identity and must bind the identities/digests of the authority it consumed. The learning cycle closes the graph: outcomes become memory and learning proposals for future planning. Automatic learning may propose; it must not silently mutate a frozen ProfileVersion.

## 3. Node envelope

Every durable authority node SHOULD expose the following logical envelope, whether stored directly or derivable from persisted fields:

```json
{
  "node_id": "stable-id",
  "node_type": "ContentSpecV1",
  "schema_version": "v1",
  "tenant_id": "...",
  "created_at": "...",
  "predecessor_ids": ["..."],
  "payload_digest": "sha256:...",
  "producer": {
    "kind": "human|deterministic-service|model|renderer|provider",
    "version": "..."
  },
  "evidence_ids": ["..."],
  "state": "..."
}
```

Successor links may be materialized or resolved through indexes, but certification evidence must prove that expected downstream nodes reference the frozen upstream authority.

## 4. Authority boundaries

### Profile and learning

`ProfileVersion` is immutable. Analytics or editorial memory may generate a `LearningProposal`; only an explicit authorized transition may create a later ProfileVersion. Old content remains bound to its historical profile digest.

### Creative planning

Model-backed candidate generation produces proposals. The deterministic planning authority owns novelty checks, memory checks, diversity, role/format constraints and the final frozen `ContentPlan`.

### Editorial production

Writer/Editor agents receive frozen Profile + plan + research + CreativeBrief. Structured output validation, evidence rules and deterministic publishability checks sit between model output and any reviewable revision.

### Visual production

`VisualSpec` is a typed intermediate representation. If generated imagery is required, the image provider returns bytes only. Those bytes are validated, stored by prodAgentic, hashed, and referenced as source assets before Chromium composes final render assets.

Remote URLs are transport inputs at most; they are never approval authority.

### QA and approval

QA reconstructs the exact render input from persisted authority and owned source assets. It must not regenerate imagery or rewrite copy during verification. Human approval freezes exact revision + QA report + owned asset hashes.

## 5. Digest law

Cryptographic digests use SHA-256 unless a later ADR replaces it. Canonical JSON intended for digesting must use one defined canonicalization method. R4 design adopts the principles of RFC 8785 JSON Canonicalization Scheme for deterministic JSON serialization; candidate implementation must either use a conforming JCS implementation or prove an equivalent constrained canonical form for the concrete payload subset.

A digest mismatch is a blocking integrity error. It is never normalized away merely to make recovery pass.

## 6. Generated media provenance

Generated image lineage binds at minimum:

- frozen VisualSpec / requirement identity;
- prompt or prompt digest;
- provider + model identifier;
- response MIME type;
- owned byte SHA-256;
- storage identity;
- generation run identity;
- exact render inputs that consumed it.

C2PA Content Credentials are treated as a forward-compatible external media provenance layer, not as a false claim of current implementation. R4’s mandatory baseline is internal owned-byte lineage and digest verification.

## 7. Supply-chain boundary

Repository/release evidence follows SLSA/in-toto principles:

`source SHA → CI workflow identity → tests/build → generated evidence/artifacts → attestation/receipt → candidate decision → merge receipt → post-merge verification`.

GitHub Artifact Attestations/Sigstore are a target for distributable build artifacts. Merely generating an attestation is insufficient; verification is part of the consuming gate.

## 8. Threat model

R4 explicitly defends against: stale Profile use; model schema escape; prompt/internal-state leakage into content; novelty bypass; unsupported claim insertion; duplicate creative ideas; remote asset mutation; provider retry generating different authority; asset substitution; digest drift after Mongo serialization; QA rebuilding different inputs; approval of a different revision than displayed; replay/duplicate publication; simulation being mistaken for production; stale candidate promotion; CI evidence from a different SHA; and documentation claiming stronger guarantees than code/tests demonstrate.

## 9. Recovery law

Recovery is a graph traversal, not regeneration by default. A retry first resolves frozen predecessor nodes and owned assets. A node may be recreated only when its contract explicitly allows replacement and the replacement receives a new identity. Immutable authority is never overwritten in-place to hide a partial failure.

## 10. Certification implication

A release is not certified because individual services are green. Certification requires that all required graph edges have tests/evidence and that product UAT proves the final package is publishable. Technical integrity and content quality are separate gates and both are blocking.

## 11. Model routing and safe failure lineage

Agents request the semantic `QUALITY_TEXT` profile. The configured primary is
`gemini-3.6-flash`; the fallback is `gemini-3.5-flash-lite`. The execution handoff
reported quota/unavailability on full Flash routes and a usable Lite route with
the same credential. This observation motivates the fallback; it does not prove
future availability or independent provider infrastructure.

`QUOTA_EXHAUSTED` may be model/tier scoped. A direct Google quota failure opens
only that model's breaker, skips further retries on that route and proceeds to
the next eligible model. Exhausting all routes produces `RoutingExhausted` and a
durable failed run. `AUTHENTICATION`, `INVALID_REQUEST`, `CANCELLED` and `UNKNOWN`
remain terminal. The Google adapter marks quota/rate-limit fallback as allowed;
SDK `RESOURCE_EXHAUSTED` on HTTP 429 is quota exhaustion even without the word
"quota" in its message.

The n8n policy is separate: quota or exhausted transport failures open its
provider breaker and do not bypass n8n unless the existing explicit bypass
policy allows it. The existing model-not-found behavior is unchanged.

Each production request and each model-backed batch-planning request uses
`ModelRouter.isolated()`. Adapters and routing configuration are reused, while
provider/model breaker dictionaries start empty. Research, Writer and Editorial
retain breaker history inside the same production request. Failures cannot
contaminate another content item or batch request through those dictionaries.

Routing remains bounded per `stream_generation` call: one transport retry per
route, one language repair across the stage, two models, five total attempts
and a 75-second transport deadline. Retry backoff consumes that same deadline.
The existing separate structured-contract repair budget remains unchanged;
each contract repair starts a new bounded router call. These are not an
end-to-end 75-second bound for the whole multi-agent HTTP request.

Model discovery is advisory to routing. A fresh successful catalog prioritizes
discovered models but never deletes configured routes. Failed, expired or absent
discovery restores configured priority. Readiness still reports its existing
catalog/dependency statuses, including NOT_READY/UNKNOWN; discovery is not proof
that a generation will succeed. Refresh failures retain the last successful
catalog and log only safe categories, never exception payloads.

`AttemptFailed.failure_code` carries the typed category into
`AgentAttemptEvidenceV1.safe_failure_code`. It accepts the provider ErrorCode
taxonomy plus `LANGUAGE_MISMATCH`; an unrecognized explicit code becomes
`MODEL_ATTEMPT_FAILED`. The legacy reason-only path remains compatible. Router
provider-failure reasons contain only a category, and stage deadline failures
carry `TIMEOUT` explicitly. Raw provider messages/responses are not durable
failure evidence. Existing run-level stage codes still bind the detailed attempt
records without changing the persistence schema.

This routing policy does not change Research NO_GO, Writer claim restrictions,
Editorial REJECT, the stricter R4 publishability floor, or human approval.
Production domain refusals remain HTTP 422 and upstream contract failures remain
HTTP 502. Production still requires explicit non-demo operation with credentials
supplied externally; missing credentials never select demo mode automatically.
