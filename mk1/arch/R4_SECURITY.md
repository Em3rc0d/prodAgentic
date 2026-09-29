# R4 Security Model — Creative Production

Status: **AUTHORITATIVE SECURITY DESIGN / IMPLEMENTATION MAY BE PARTIAL**

## Security objective

R4 must improve creative capability without widening authority. Model providers, image providers, renderer transport, analytics and recovery mechanisms are all untrusted inputs or execution surfaces until their output is validated against prodAgentic-owned contracts.

## Trust zones

```text
Human authority
  ↓
prodAgentic application/domain contracts
  ↓
owned persistence + AssetStore + digests
  ↓
controlled renderer / CI
  ↓
external model/image/provider services
```

Authority flows downward only through explicit requests; untrusted provider output flows upward only after validation and normalization.

## Secret boundary

Secrets never enter Profile snapshots, CreativeBrief, ContentSpec, VisualSpec, generated-image prompts, Review packages, analytics events, evidence artifacts or browser-visible JSON.

Secrets/OAuth/provider credentials remain configuration/runtime-only. Schemas must be allowlisted and reject unexpected fields. Logs and errors must redact credentials and authorization headers.

## Provider isolation

Text/image providers receive the minimum bounded input needed for their role. Provider responses are treated as data, not instructions.

Controls:

- structured-output validation for text/plan proposals;
- MIME/magic/size verification for binary image output;
- no provider-controlled storage key or public URL becomes authority;
- provider/model identifiers are persisted as metadata for lineage;
- retries respect idempotency/frozen authority rules;
- failures remain observable and do not silently downgrade production into demo.

## Prompt/internal-state leakage

Publishability policy blocks model-visible implementation terminology, control tokens, schema identifiers, demo/test markers and workflow instructions from public content.

No hidden chain-of-thought is required or stored as product authority. Persist concise model decision metadata, structured reasons and evidence references instead.

## Asset security

Generated/source assets are accepted only after validation and are stored under product ownership. Authoritative rendering must not fetch arbitrary remote media.

Asset receipt binds MIME, byte size, SHA-256, storage key, generation run and VisualSpec requirement. Mismatched bytes/digest are blocking integrity failures.

## Renderer boundary

Renderer accepts typed VisualSpec + resolved owned asset inputs. It must not become a generic browser proxy.

Required constraints:

- no arbitrary remote navigation for authoritative render;
- no uncontrolled script injection from model output;
- bounded dimensions/page count/input sizes;
- explicit font/layout contract;
- render timeout and failure classification;
- output bytes rehashed after render before persistence/approval.

## Multi-tenant boundary

Every durable authority object carries tenant/workspace ownership directly or through an immutable parent chain. Fetch-by-ID operations must verify tenant scope rather than relying on opaque IDs being unguessable.

Cross-tenant Profile, content, source asset, render asset, QA, approval or analytics linkage is a blocking invariant violation.

## Replay and duplicate action protection

Publication/export side effects require idempotency identity derived from approved authority. A retry must determine whether the side effect already happened before creating another external action.

Approvals are immutable; replaying an approval request does not create a second semantic approval for the same exact bundle.

## Recovery security

Recovery first resolves persisted immutable predecessors. It does not regenerate or substitute missing authority merely to continue the workflow.

If owned bytes are missing or corrupted, recovery fails closed and surfaces the broken node. It must not call the provider to recreate a visually similar asset under the old digest/identity.

## Analytics and learning safety

Analytics may influence operational learning only through typed proposals and policy. Sensitive personal characteristics are not inferred into Profile authority from engagement data.

Semantic Profile changes require human approval. Rejected learning proposals remain auditable and should not be repeatedly resurfaced without materially new evidence.

## CI/release security

R4 release identity is the exact Git SHA. Evidence from another SHA, branch name or later rerun cannot certify it.

Candidate promotion requires expected workflow/check identities, product UAT and graph verification. Supply-chain attestations, when added, must be verified against repository/workflow/source identities rather than accepted because a signed file exists.

## Abuse/failure classes

Security tests must cover at least:

- schema escape / unexpected model fields;
- internal prompt/state leakage;
- malicious or malformed image bytes;
- oversized provider response;
- remote URL injection into renderer;
- asset substitution/digest mismatch;
- cross-tenant reference attempts;
- stale revision approval;
- repeated publication/export requests;
- missing/corrupt source asset during recovery;
- simulation artifact presented as production;
- exact-SHA evidence mismatch.

## Security claim boundary

R4 may claim only controls demonstrated by implementation + tests. Design documents are intended guarantees, not proof that every control is already enforced.
