# MK1 Security and Observability

Status: **FROZEN BASELINE**

# Security

## Tenant isolation

All new repository methods require TenantContext or derive it through an application service. Raw repository helpers that query business collections without tenant scope are prohibited except explicit migration/admin tooling.

Automated tests must include cross-tenant negative cases.

## Authentication compatibility

MK0 single-admin session auth may remain during early migration. MK1 domain tenancy is introduced independently so future multi-user/RBAC changes do not require re-keying every entity.

A bootstrap deployment may map the authenticated admin to one bootstrap Tenant.

## Authorization

V1 permissions at minimum distinguish:

- authenticated tenant operator;
- system worker identity;
- provider callback/service identity where required.

Future team roles may extend this without changing Approval actor/audit contracts.

## Secrets

- provider tokens/client secrets encrypted at rest where stored;
- secret decryption limited to adapter boundary;
- never logged;
- never copied into agent prompts;
- never copied into ProfileVersion/Approval/export manifest;
- diagnostics show readiness/status, not secret values.

## Research and prompt-injection boundary

External documents/web pages are untrusted evidence. Agent system instructions explicitly treat retrieved content as data.

Research tooling must:

- separate source text from instructions;
- preserve source identity;
- reject attempts by source content to redefine agent/system policy;
- constrain tool permissions by agent role.

## Asset ingestion

Remote/user assets require:

- MIME/content validation;
- maximum size;
- image dimension limits;
- safe filename/storage key generation;
- no path traversal;
- network fetch allow/deny controls against SSRF-sensitive hosts;
- timeouts;
- malware scanning hook where deployment risk requires it.

## CSRF/session baseline

Retain MK0's secure session/CSRF principles until replaced by an explicitly stronger auth architecture.

# Observability

## Correlation identifiers

Carry where applicable:

```text
tenant_id
profile_id
batch_id
content_id
run_id
revision_id
job_id
approval_id
schedule_id
publication_id
```

## Metrics

### Product/agent

- batch planning latency;
- candidate rejection/replacement counts;
- agent latency per role;
- contract repair count;
- token/cost estimates;
- QA fail/recovery rates;
- render latency.

### Transport

- Redis stream lag;
- pending entries;
- oldest job age;
- DLQ count;
- outbox backlog;
- dispatcher delay.

### Publication

- claim conflicts;
- publish latency;
- known-safe failures;
- reconciliation-required count/age;
- duplicate-prevention no-ops;
- provider health.

### Assets

- write/read failures;
- digest mismatch;
- storage usage;
- missing asset attempts.

### Analytics

- sync success;
- freshness lag;
- rate-limit/degradation.

## Logs

Structured JSON preferred in production. Log event names + identifiers + safe error classification. Avoid full prompt/content payloads unless explicitly enabled in a secure diagnostic environment.

## Tracing

OpenTelemetry-compatible spans are recommended around:

- request/use case;
- model route/attempt;
- renderer;
- Mongo operation groups;
- Redis enqueue/consume;
- provider calls.

Traces are observability, not source-of-truth evidence.

## Health model

Expose distinct health dimensions:

```text
api
mongo authority
redis transport
asset store
model providers
renderer
platform connections
analytics freshness
```

User-facing health collapses these into capability impact; operations may inspect each dimension.

## Cost controls

Tenant/plan policy can cap:

- candidate pool refill;
- agent retries;
- model profile selection;
- generated visual variants;
- analytics frequency.

Cost control may degrade optional quality/latency paths but cannot bypass safety/approval invariants.
