# prodAgentic Commercial V1 — launch contract

Status: reconciliation candidate for assisted private pilots.

## Product we are selling

Commercial V1 is a **LinkedIn-first trusted content-production system** for an operator who wants AI assistance without handing publication or factual authority to the model.

The customer outcome is not “generate text.” It is:

> turn real knowledge, decisions and experience into content worth reading, while preserving inspectable evidence for the factual claims that survive human review and approval.

The governing product principle is:

> **prodAgentic does not invent a better story. It finds the best story the evidence already contains.**

Commercial V1 therefore has two inseparable halves:

- **Value Engine** — discover and express something worth attention.
- **Trust Engine** — prove what the content is allowed to claim and preserve human authority.

## Intended first customer profile

Commercial V1 is best suited to an individual professional, founder, consultant, technical creator or small operator who:

- publishes through one LinkedIn member identity;
- wants a repeatable content workflow rather than isolated prompts;
- values explicit human review before publishing;
- wants factual claims tied to inspectable source/evidence material;
- benefits from reusable positioning/voice constraints;
- wants scheduling and publication evidence;
- is comfortable with an assisted onboarding/deployment rather than self-service SaaS.

This release is not positioned as an enterprise multi-tenant platform.

## Included in Commercial V1

- reusable Content Profiles;
- research, writing, editing and visual agent stages;
- durable ContentRun lifecycle and stage evidence;
- review/edit workflow;
- `SourcePacket` / `EvidenceRef` evidence boundary for grounded content;
- claim taxonomy for facts, inferences, opinions, experiences, estimates and predictions;
- deterministic Grounding policy with hard blocks for contradiction or insufficient evidence;
- explicit human Grounding verification bound to exact content and assessment hashes;
- edit-driven invalidation of stale Grounding;
- fail-closed approval when current Grounding is not `PASS + VERIFIED`;
- immutable approval bundle containing Grounding provenance digests;
- LinkedIn OAuth connection;
- text and visual LinkedIn publishing;
- scheduling through the shared publication coordinator;
- exact author-scoped duplicate-publication prevention;
- conservative reconciliation for ambiguous provider outcomes;
- exact Content Memory for review/published content;
- server-resolved workspace scope;
- single-host Docker deployment topology;
- authenticated application/CSRF boundary;
- sanitized runtime release-receipt tooling.

## Explicitly outside Commercial V1

The Grounding **authority/lifecycle boundary is included**, but fully autonomous semantic truth determination is not claimed. Commercial V1 still relies on explicit human verification of the claim-to-evidence map.

Outside V1:

- autonomous semantic Grounding without human verification;
- general-purpose Knowledge Sources / continuous source ingestion;
- semantic embeddings or semantic duplicate detection;
- Odyssey ingestion;
- Personal Content Graph;
- automatic voice learning;
- analytics-driven editorial learning;
- X, Medium, newsletter or other publication channels;
- autonomous posting without approval;
- multi-user workspace membership/RBAC;
- per-customer billing inside the application;
- multi-host failover or distributed publication workers.

These are roadmap items, not sales claims.

## Commercial model for the first pilots

The initial commercial motion is **assisted onboarding / private paid pilot**. Pricing, billing cadence and any service-level commitments are agreed outside the application in the applicable order form or pilot agreement. prodAgentic does not currently claim an in-product billing system.

This lets the product begin generating commercial evidence before prematurely building subscription infrastructure.

## Local content-quality qualification before deployment

Deployment is not sufficient evidence that prodAgentic is valuable.

Before treating Commercial V1 as commercially interesting, the local system must be evaluated against a Golden Content Set built from real project/working evidence. The goal is to measure two independent properties:

1. **Editorial value** — would the operator genuinely want to publish the result?
2. **Factual faithfulness** — does the result remain within the evidence and correctly distinguish fact, inference and opinion?

A technically valid but generic post is a product-quality failure. A highly engaging post containing fabricated significance is a trust failure.

The desired loop is:

```text
real evidence
  -> SourcePacket
  -> angle discovery
  -> writing/editing
  -> attention quality
  -> claim extraction
  -> Grounding
  -> human verification
  -> human content approval
```

No LinkedIn side effect is needed to run this local qualification.

## Assisted onboarding

For each pilot:

1. identify the operator and intended LinkedIn publishing identity;
2. provision an isolated deployment/environment;
3. generate independent application/session/token-encryption secrets;
4. configure a server-owned workspace ID;
5. create the initial Content Profile with the operator;
6. connect LinkedIn through OAuth;
7. verify the connection using sanitized status/receipt evidence;
8. create one grounded test ContentRun from explicit evidence;
9. inspect the claim/evidence map and record Grounding `VERIFIED` only when the operator accepts it;
10. review the final content and approve explicitly;
11. validate scheduling or publication only with the operator's authorization;
12. retain the sanitized release receipt;
13. document support/escalation ownership for that pilot.

No customer should be asked to send access tokens, OAuth authorization codes, session cookies or application secrets through chat/email.

## Production acceptance gates

A pilot may be treated as production-ready only when all applicable gates are green on the exact release candidate:

### Repository

- backend tests pass;
- Python production lock installs with hashes;
- locked production dependencies pass security audit;
- frontend tests/lint/build pass;
- shipped frontend dependency audit passes;
- browser certification passes on desktop and mobile;
- complete Docker stack certification passes;
- exact candidate is based on current `main` with no unresolved divergence.

### Content intelligence / Grounding

- final content has a persisted SourcePacket in the authoritative workspace;
- claim extraction is complete for the revision being reviewed;
- Grounding assessment SHA matches exact final-content SHA;
- deterministic Grounding policy returns `PASS`;
- contradicted or insufficiently supported factual claims cannot pass;
- supported inferences remain visible to the reviewer;
- explicit human Grounding review is `VERIFIED` for the exact assessment/content revision;
- any subsequent content edit invalidates the old assessment/review;
- approval freezes Grounding provenance digests into its immutable bundle.

### Runtime

- HTTPS public origin is canonical;
- production config validates fail-closed;
- auth is enabled;
- cookie is Secure with the deployment-appropriate SameSite policy;
- Mongo is durable across restart;
- approved visual storage is durable across restart;
- only the intended gateway/public ports are externally reachable;
- backups and recovery ownership are defined for the pilot environment.

### LinkedIn

- OAuth reports `CONNECTED`;
- required scopes are present;
- token remains decryptable and unexpired;
- persisted author identity matches publication evidence;
- a previously authorized real publication has a persisted LinkedIn post URN, or a new smoke is explicitly authorized;
- approval bundle and publication bundle match;
- stored publication fingerprint/dedupe evidence is consistent;
- visual bytes match the approved digest when a visual was published.

Use:

```bash
cd backend
python tools/release_receipt.py --run-id <published-run-id>
```

The verifier performs no LinkedIn HTTP request.

## Security rules for operators

- Never commit `.env` or deployment secrets.
- Never collect a LinkedIn access token from the customer manually for normal production use.
- Never copy OAuth callback `code` or `state` values into tickets, chat or release receipts.
- Never mark Grounding `VERIFIED` merely because a model classified a claim as grounded.
- Never approve content with stale or blocked Grounding.
- Never retry a `RECONCILIATION_REQUIRED` publication automatically.
- Never bypass approval to speed up a demo.
- Never expose MongoDB or FastAPI directly when using the provided gateway topology.
- Rotate application/session/token-encryption secrets if disclosure is suspected.
- Treat production logs, SourcePackets and database exports as potentially sensitive operational data.

## Support and incident posture

Commercial V1 is an assisted product. Until self-service tenancy, billing and automated recovery exist, each pilot must have a named operational owner outside the repository who can:

- provision and rotate secrets;
- inspect health and logs;
- inspect and correct Grounding evidence when the system blocks a claim;
- reconnect LinkedIn when required;
- reconcile ambiguous publication outcomes manually;
- restore Mongo/assets from the deployment's backup system;
- communicate service-impacting incidents to the customer.

## What makes a pilot successful

Measure product value before building more platform surface. Useful pilot signals include:

- percentage of generated outputs the operator would genuinely publish;
- time from evidence/idea to approved post;
- percentage of factual claims passing Grounding without manual factual repair;
- frequency and cause of `INSUFFICIENT_EVIDENCE` / `CONTRADICTED` claims;
- amount of human editing before approval;
- repeat use of Content Profiles;
- scheduling/publishing success rate;
- duplicate/reconciliation incidents;
- whether the operator returns to create the next piece of content.

Once real LinkedIn analytics are available, attention and profile-visit signals can be compared with the local editorial-quality predictions. No automated analytics-learning feature is required to begin collecting those observations manually.

## Exit criteria from assisted pilot to broader SaaS

Do not widen distribution merely because the stack is deployable. A broader self-service launch should wait for evidence that the core workflow is repeatedly valuable and for at least:

- measured Golden Content Set quality demonstrating both editorial value and faithfulness;
- multi-user/workspace authorization model;
- customer-safe provisioning and secret lifecycle;
- billing/entitlement model;
- backup/recovery automation appropriate to the hosting model;
- operational monitoring/alerting;
- final legal/compliance review for the intended markets;
- support process that does not depend on direct database intervention for routine use.
