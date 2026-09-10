# S11 FORMALIZATION — Analytics Snapshots

Status: **FROZEN FOR IMPLEMENTATION**

Base authority:

`main@0b72c09de2c6c48d57c829e53c021493eed8885d`

S10 Calendar + LinkedIn Publication is `CERTIFIED/CLOSED` at this authority.

## Objective

Transfer analytics measurement into MK1 as append-only, tenant-scoped evidence without making provider payloads or mutable counters authoritative.

Canonical flow:

```text
Publication(PUBLISHED)
→ analytics intent/outbox
→ Redis pa:analytics:v1
→ analytics worker
→ PlatformAnalyticsAdapter
→ MetricSnapshotV1 (append-only Mongo)
→ Analytics read model/UI
```

S11 does not implement planner learning. S12 consumes normalized S11 snapshots through a separate PerformanceSummary boundary.

## Frozen authority rules

1. Only a `PublicationV1` with state `PUBLISHED` and a persisted provider receipt can produce automatic analytics work.
2. Analytics never reads mutable drafts or ContentItem fields as provider identity.
3. `MetricSnapshotV1` is append-only evidence. Existing snapshots are never rewritten to represent newer provider state.
4. Missing, unsupported, unauthorized or provider-omitted metrics are `UNAVAILABLE`, never coerced to numeric zero.
5. A provider failure never zeroes previous successful observations.
6. Every snapshot binds tenant, publication, provider, external post identity, provider API version, observation time and collection attempt identity.
7. Raw provider metric names are retained in a bounded representation; normalization occurs only when semantics are defensible.
8. Redis is transport only. Mongo outbox + Mongo snapshot documents remain durable authority.
9. Duplicate transport delivery may repeat a safe read call if a prior attempt has no persisted completion evidence, but one deterministic collection operation may persist at most one snapshot.
10. Publication capability and analytics capability are independent. A LinkedIn connection may remain publish-capable while analytics is unavailable.
11. S11 V1 automatic LinkedIn metrics are limited to the five query types explicitly documented for single-post `q=entity`: `IMPRESSION`, `MEMBERS_REACHED`, `RESHARE`, `REACTION`, `COMMENT`.
12. Additional documented metric names such as saves/clicks are not promoted into automatic S11 V1 until their query contract is independently proven.
13. Analytics provider reads are side-effect-free; no live-publication authorization is required for contract certification. A live provider read still requires legitimate credentials and granted analytics scope.

## LinkedIn provider contract

Current provider surface verified for S11 formalization:

- endpoint: `GET /rest/memberCreatorPostAnalytics`;
- finder: `q=entity`;
- entity: the exact LinkedIn post/share URN from the S10 publication receipt;
- query types: `IMPRESSION`, `MEMBERS_REACHED`, `RESHARE`, `REACTION`, `COMMENT`;
- aggregation: `TOTAL` for S11 V1 snapshots;
- required scope: `r_member_postAnalytics`;
- standard versioned REST headers remain required (`Linkedin-Version`, `X-Restli-Protocol-Version: 2.0.0`).

Provider documentation authority checked during formalization:

- LinkedIn Member Post Statistics, Marketing API view 2026-08;
- LinkedIn Increasing Access, Community Management API permissions.

The scope is independent from `w_member_social`. Existing S10 publication must not be disabled merely because analytics consent is absent.

## Capability model

Extend platform capability/readiness with analytics-specific evidence rather than overloading publish readiness.

Minimum fields:

```text
analytics_available: bool
analytics_reason: str | null
analytics_scope_granted: bool
analytics_metrics_supported: list[str]
analytics_last_success_at: datetime | null
```

The UI must distinguish at least:

- Connected + analytics ready
- Connected + analytics permission missing
- Analytics stale
- Analytics provider degraded
- No published content yet

## Domain model

### MetricValueV1

```text
metric
availability: AVAILABLE | UNAVAILABLE
value: non-negative integer | null
provider_metric
reason: str | null
```

Invariant: `AVAILABLE` requires a numeric value. `UNAVAILABLE` requires `value=null`.

### MetricSnapshotV1

Required identity/evidence:

```text
snapshot_id
operation_key
tenant_id
publication_id
provider
external_post_id
provider_api_version
observed_at
collected_at
metrics[]
raw_digest
created_at
```

`operation_key` is deterministic from:

```text
operation_version
+ tenant_id
+ publication_id
+ provider
+ external_post_id
+ collection_window/bucket
```

The operation key prevents duplicate persistence for one scheduled observation while later observations append new snapshots through a different collection bucket.

## Collection cadence and freshness

S11 V1 uses explicit collection intents, not an unbounded polling loop.

Default automatic observation windows after successful publication:

```text
T+1h
T+24h
T+72h
T+7d
```

A delayed worker may collect a due window late but records actual `collected_at` and intended window/bucket. No snapshot is fabricated for a missed window.

Freshness surfaces the latest successful `collected_at`. UI staleness is derived from evidence; it is never inferred as zero activity.

The cadence is configuration/policy and may be changed later without altering snapshot semantics.

## Failure classification

### Safe non-success

- analytics scope absent;
- unsupported provider/metric;
- publication has no provider post identity;
- provider proves authorization failure/rejection;
- malformed provider payload before persistence.

Record degraded collection evidence; do not write a fake zero snapshot.

### Retryable transport/provider read

- 429 with retry-after policy;
- provider 5xx;
- timeout/network loss on a side-effect-free analytics GET.

Because the provider call is read-only, bounded retry is safe. Retry exhaustion must not modify previous snapshots.

### Persistence uncertainty

If provider read succeeds but snapshot persistence outcome is uncertain, deterministic `operation_key` + unique Mongo index allows retry without duplicate snapshot authority.

## OAuth migration/upgrade

Current S10 connection documents already persist granted scopes.

S11 adds analytics permission awareness without mutating existing connection authority:

- existing connection lacking `r_member_postAnalytics` remains publish-capable;
- Analytics UI exposes a low-friction "Enable analytics" reconnect/upgrade action;
- OAuth authorization may request the additional scope when analytics enablement is explicitly chosen;
- token replacement remains encrypted infrastructure-only;
- failure/refusal to grant analytics scope does not disconnect publishing unless provider semantics require a full reauthorization failure.

No secret or raw token appears in analytics documents, logs, API responses or evidence artifacts.

## Persistence

New Mongo collections:

```text
metric_snapshots_v1
analytics_collection_attempts_v1
```

S9 outbox is reused for durable analytics intents. A dedicated specialization filters only `analytics.linkedin.v1` into `pa:analytics:v1`.

Indexes must include:

- unique `(tenant_id, snapshot_id)`;
- unique `(tenant_id, operation_key)`;
- query `(tenant_id, publication_id, collected_at desc)`;
- query `(tenant_id, provider, collected_at desc)`.

## API surface

Minimum S11 API:

```text
GET  /api/analytics/overview
GET  /api/analytics/publications/{publication_id}/snapshots
POST /api/analytics/publications/{publication_id}/collect
POST /api/connections/linkedin/analytics/enable
```

Manual collect creates durable intent; it does not synchronously call LinkedIn from the request route.

Clients never submit provider post IDs, raw metrics or arbitrary tenant IDs.

## Analytics UI

Primary route: `/analytics`.

V1 sections:

- Overview
  - published content count
  - available impressions/views evidence
  - available interactions
  - freshness/degradation
- Publication evidence list
  - latest snapshot age
  - available metrics only
  - explicit `Unavailable` values/reasons
- Capability card
  - analytics permission/readiness
  - enable/reconnect action when needed

No vanity ranking, streaks or pressure UI. S11 is evidence for decisions, not a dopamine dashboard.

Content-pattern aggregation and confidence-aware recommendations belong to S12 unless they are simple descriptive read-model projections with no learning claim.

## Observability

Required evidence/metrics:

- analytics intents due/age;
- collection attempts by outcome class;
- provider duration/status class;
- rate-limit events;
- snapshot append count;
- duplicate operation conflicts;
- unavailable metric counts by reason;
- latest successful collection age;
- analytics capability readiness by provider;
- zero secret leakage.

## Risks touched

- provider analytics API/version drift;
- missing/revoked analytics permission;
- accidental zero-coercion;
- duplicate snapshots under at-least-once transport;
- cross-tenant analytics leakage;
- stale data presented as current;
- provider rate limiting;
- accidental coupling of publishing readiness to analytics readiness.

## Required certification matrix

S11-CERT must prove on one exact candidate SHA:

1. MetricValue availability invariants;
2. MetricSnapshot tenant isolation and append-only behavior;
3. deterministic operation identity + duplicate persistence safety;
4. only PUBLISHED Publication with receipt can enqueue analytics;
5. dedicated S9 outbox/Redis analytics transport recovery;
6. LinkedIn five-query contract + required headers;
7. missing analytics scope degrades without disabling publication;
8. provider 429/5xx/timeout bounded retry without zeroing prior evidence;
9. unavailable provider metric remains null/unavailable;
10. freshness derived from last successful snapshot;
11. Analytics desktop/mobile UI renders unavailable/stale states honestly;
12. no token/secret in snapshot/API/evidence;
13. clean exact-SHA checkout and source inventory.

Base CI + Docker + S3-S10 regression workflows must also remain green on the same candidate SHA.

## Implementation sequence

```text
S11.0 Formalization + provider permission boundary       CLOSED BY THIS RECORD
S11.1 MetricSnapshot domain + Mongo repository          NEXT
S11.2 Analytics capability + OAuth scope upgrade        LOCKED
S11.3 LinkedIn analytics adapter                        LOCKED
S11.4 S9 analytics outbox + Redis worker                LOCKED
S11.5 Collection policy + initial scheduling            LOCKED
S11.6 Analytics API/read model                          LOCKED
S11.7 Analytics UX                                      LOCKED
S11.8 Chaos/security/browser certification              LOCKED
S11.9 exact-SHA pre-merge consensus                     LOCKED
S11.10 merge + post-merge consensus                     LOCKED
```

## Closeout law

S11 is `CERTIFIED/CLOSED` only after:

1. all S11 and regression gates are green on one exact candidate SHA;
2. merge uses the exact certified head SHA;
3. all applicable workflows are green again on the resulting exact `main` SHA.

Implementation completion is not certification.
