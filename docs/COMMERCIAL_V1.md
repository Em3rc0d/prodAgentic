# prodAgentic Commercial V1 — launch contract

Status: reconciliation candidate for assisted private pilots.

## Product we are selling

Commercial V1 is a **LinkedIn-first trusted content-production system** for an operator who wants AI assistance without handing publication authority to the model.

The customer outcome is not “generate text.” It is:

> turn working knowledge and ideas into reviewed, approved, scheduled or published LinkedIn content with durable evidence of what happened.

## Intended first customer profile

Commercial V1 is best suited to an individual professional, founder, consultant, technical creator or small operator who:

- publishes through one LinkedIn member identity;
- wants a repeatable content workflow rather than isolated prompts;
- values explicit human review before publishing;
- benefits from reusable positioning/voice constraints;
- wants scheduling and publication evidence;
- is comfortable with an assisted onboarding/deployment rather than self-service SaaS.

This release is not positioned as an enterprise multi-tenant platform.

## Included in Commercial V1

- reusable Content Profiles;
- research, writing, editing and visual agent stages;
- durable ContentRun lifecycle and stage evidence;
- review/edit workflow;
- explicit immutable approval;
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

- semantic embeddings or semantic duplicate detection;
- source grounding / Knowledge Sources;
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

## Assisted onboarding

For each pilot:

1. identify the operator and intended LinkedIn publishing identity;
2. provision an isolated deployment/environment;
3. generate independent application/session/token-encryption secrets;
4. configure a server-owned workspace ID;
5. create the initial Content Profile with the operator;
6. connect LinkedIn through OAuth;
7. verify the connection using sanitized status/receipt evidence;
8. create one test ContentRun and review it manually;
9. approve explicitly;
10. validate scheduling or publication only with the operator's authorization;
11. retain the sanitized release receipt;
12. document support/escalation ownership for that pilot.

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
- Never retry a `RECONCILIATION_REQUIRED` publication automatically.
- Never bypass approval to speed up a demo.
- Never expose MongoDB or FastAPI directly when using the provided gateway topology.
- Rotate application/session/token-encryption secrets if disclosure is suspected.
- Treat production logs and database exports as potentially sensitive operational data.

## Support and incident posture

Commercial V1 is an assisted product. Until self-service tenancy, billing and automated recovery exist, each pilot must have a named operational owner outside the repository who can:

- provision and rotate secrets;
- inspect health and logs;
- reconnect LinkedIn when required;
- reconcile ambiguous publication outcomes manually;
- restore Mongo/assets from the deployment's backup system;
- communicate service-impacting incidents to the customer.

## What makes a pilot successful

Measure product value before building more platform surface. Useful pilot signals include:

- time from idea to approved post;
- percentage of generated runs reaching approval;
- amount of human editing before approval;
- repeat use of Content Profiles;
- scheduling/publishing success rate;
- duplicate/reconciliation incidents;
- whether the operator returns to create the next piece of content.

No analytics feature is required to begin collecting these pilot observations manually.

## Exit criteria from assisted pilot to broader SaaS

Do not widen distribution merely because the stack is deployable. A broader self-service launch should wait for evidence that the core workflow is repeatedly valuable and for at least:

- multi-user/workspace authorization model;
- customer-safe provisioning and secret lifecycle;
- billing/entitlement model;
- backup/recovery automation appropriate to the hosting model;
- operational monitoring/alerting;
- final legal/compliance review for the intended markets;
- support process that does not depend on direct database intervention for routine use.
