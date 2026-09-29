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
EvidenceBundle           │
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


## R4.1 — reliability and evidence authority

Implementation branch: `r4.1-reliability-evidence-authority`, based exactly on
`dc9e072846b94b6476ff8c246e83388df10dad7b`. This section supersedes earlier R4
assumptions about Research having no external evidence and blanket failed-item
retries. It describes implementation, **not executed verification or certification**.

### Acquisition and research

The production factory requires `EvidenceAcquisitionPort`. `GoogleGroundingEvidenceProvider`
uses the existing Gemini client with native `google_search`. Only SDK
`grounding_chunks` joined to `grounding_supports` may introduce source identities.
An ordinary model-generated URL or bibliography cannot become evidence.

Each `EvidenceSourceV1` bounds locator/title/excerpt, records retrieval time,
provider/model and attribution indices, and verifies its excerpt SHA-256.
`EvidenceBundleV1` binds tenant, exact plan identity/digest, query digest, bounded
sources, acquisition status and a 24-hour acquisition validity window. Bundle
payloads are stored as JSON to preserve canonical timestamp precision.

Provider-grounded segments are explicitly **secondary summaries**, not verbatim
page excerpts, downloaded documents or independently verified facts. Redirect
hosts are recorded as locator domains; original publisher identity is unverified
and canonical URL remains null. Sources cannot promote themselves to primary trust.
Missing metadata yields an INSUFFICIENT bundle; Research remains responsible for
NO_GO. Transport/authentication failures remain distinct from insufficient evidence.

Research receives the exact bundle and includes it in attempt input digests.
`ResearchPackV1` binds bundle ID and digest; copied EvidenceRef metadata must equal
an acquired reference. Allowed/qualified factual claims must reference acquired
sources; unsupported factual claims must be forbidden. Semantic support still
requires the Research/Editor judgment and human review; ID membership is not a
proof that a sentence is true. Writer/editor policy and approval authority remain.

QA and human approval reload and verify bundle digest, tenant, plan, source-run
ownership, ResearchPack ownership and reciprocal references. Human-edit forks carry
the same evidence authority. Historical ResearchPack objects without bundle fields
retain their original serialized shape; legacy/demo artifacts are never relabelled
as R4.1 evidence-backed outputs. R4.1 production service construction requires an
acquisition provider. Historical data is not rewritten in place.

### Route and repair budgets

The stage limit remains 75 seconds. A route receives a fair bounded share of the
remaining stage time, reserving up to 10 seconds per eligible fallback. Individual
attempts are capped at 25 seconds. Transport retry, language repair, model fallback
and provider fallback have separate decisions. Same-route repairs share the route's
slice. Attempts as well as time are reserved for fallbacks.

A structured invocation owns a single deadline/attempt/language budget across
contract repair cycles. Invalid structured output therefore cannot reset the stage
clock. `MODEL_TIMEOUT` opens the model breaker and advances to another eligible
route; `STAGE_TIMEOUT` means the global stage clock expired. Exhaustion also
preserves the last safe cause instead of collapsing quota, language and transport
errors. Google quota remains model-scoped. Request isolation remains, and n8n
no-bypass remains enforced. Native Google evidence acquisition is unavailable when
n8n is configured without direct fallback; it does not silently bypass n8n.

The text-production API also supplies a request-local 150-second provider-work
deadline, inherited by stage allocators. This bounds cumulative provider work below
the existing 180-second client timeout; it is not a database/network availability
guarantee. No provider deadline increase was used to conceal the original failure.

Language validation uses human-facing structured fields and strips technical
content. Source metadata, IDs, enum values, JSON keys, schemas, code and URLs do not
vote as prose. True wrong-language prose still emits LANGUAGE_MISMATCH and is
subject to bounded semantic repair. Ambiguous short text remains indeterminate.

### Recovery authority

| Situation | Durable action | Behavior |
| --- | --- | --- |
| Failed text run with a known transient cause | RETRY_PRODUCTION | CAS claim of FAILED item; new GenerationRun with retry_of_run_id; exact profile and plan preserved |
| Research NO_GO / editorial rejection / exhausted editorial revision budget | REPLAN_CONTENT | New candidate, content identity and ContentPlan; original failure and plan retained |
| Valid persisted downstream revision, open recoverable run | RESUME_PIPELINE | Continue visual/render/QA through their existing authority gates |
| Contract/integrity/authentication failure or unclassified failure | HUMAN_ACTION_REQUIRED | No blind retry offered |
| Cancelled or already replaced idea | NONE | No retry of historical work |

Text retry reuses an intact, unexpired EvidenceBundle. Expiration causes a new
immutable acquisition; mismatch causes a safe stop. Mongo production updates reject
terminal FAILED/CANCELLED runs. Agent attempts are persisted before terminal failure.
Existing retryable render failures keep the run in RENDERING and use RESUME_PIPELINE;
this is distinct from reopening a FAILED run.

Replacement uses unused candidates from the original governed pool, the frozen
ProfileVersion, refreshed editorial memory, the novelty engine and R4 batch
semantic-distinctness checks. Original/rejected/replacement ideas all participate
in collision checks. It does not weaken novelty to fill the requested batch size.
An exhausted pool returns a conflict, not a fabricated successful replacement.

`ReplacementPlanV1` includes rejected content/plan/run identities, predecessor
digests, exact failure, trace digest, current memory IDs, fresh novelty result and
the complete new item/plan. A tenant-scoped batch ledger appends this record with
one atomic version CAS (the first append also uses a deterministic unique document
identity). Recovery reads do not create empty ledgers. Typed records validate
item/plan/failure/novelty relationships before persistence. Concurrent replacement requests recompute against the new
ledger; duplicate retries retrieve the existing result. Ledger size is bounded at
120 records per batch. Item/plan materialization is idempotent and restartable from
the immutable record, without requiring Mongo replica-set transactions.

Batch reads materialize pending replacements and project active leaves; historical
FAILED items remain available separately. The requested batch size is not enlarged
by historical attempts. New planning traces persist JSON timestamps. Historical
traces whose canonical digest cannot be reconstructed (including older BSON
precision loss) cannot authorize replacement; they remain unchanged.

The UI uses per-item persisted recovery decisions, rechecks server state on click,
shows the safe reason, and retains `/create?batch=...` for reload. Recovery has the
same tenant/auth/CSRF boundaries as existing production routes.

### Safe operations and certification boundary

Failures expose code, stage, retryable, recovery_action, safe_message and available
content/run identity. Text and render 502 responses include these safe details.
Production logs include IDs, stage, safe category, model and fallback status where
agent attempts exist. No raw prompt, raw provider output, provider exception body,
API key or credential is logged/persisted by the new evidence path. Only bounded
normalized evidence and metadata are retained; Google Search widget HTML and raw
responses are not stored or rendered.

The acquisition port adds no new external subscription or credential. Native
Gemini search can have provider usage charges/quotas. Availability, grounding
quality and provider-specific usage/display requirements must be assessed during
Jett's real-provider audit. This implementation does not claim those gates passed.
The provider integration follows [Google's generateContent grounding contract](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
(metadata semantics consulted 2026-09-16).

A process dying between the item claim and durable run creation still requires
operator reconciliation; this change does not introduce a distributed worker lease
or claim arbitrary crash recovery. Likewise, static source inspection is not
runtime evidence. Tests, CI, UAT, browser validation and deployment were expressly
not executed in this implementation handoff.
