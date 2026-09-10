# S11 BUILD RECORD — Analytics Snapshots

Status: **IMPLEMENTATION COMPLETE — certification pending**

## Authority

Base: `main@0b72c09de2c6c48d57c829e53c021493eed8885d`  
Formalization: `mk1/build/slices/S11/FORMALIZATION.md`

## Objective

Implement tenant-scoped append-only analytics evidence from S10 `PUBLISHED` Publication authority through S9 durable transport into `MetricSnapshotV1`, then expose an honest freshness-aware Analytics UI.

## Accepted dependencies

- S9 Redis Streams + Mongo outbox
- S10 Publication/Connection authority
- `mk1/arch/ANALYTICS_LEARNING.md`
- `mk1/arch/INVARIANTS.md` analytics invariants 32–34
- ADR-0011 snapshot analytics with bounded learning
- AS-12 Analytics partial data

## Implemented surfaces

```text
backend/domain/analytics/
backend/application/analytics/
backend/infrastructure/mongo/analytics.py
backend/infrastructure/mongo/analytics_jobs.py
backend/infrastructure/mongo/analytics_publications.py
backend/infrastructure/linkedin/analytics.py
backend/infrastructure/linkedin/oauth.py
backend/workers/analytics.py
backend/routes/analytics_v1.py
backend/main.py
backend/tests/test_s11_analytics.py
frontend/app/analytics/
frontend/lib/analytics.ts
frontend/e2e/s11-analytics.spec.ts
docker-compose.s11.yml
.github/workflows/s11-cert.yml
```

S11 does not store analytics counters in `ContentItem`, `Publication`, or legacy `content_runs`.

## Frozen implementation properties

- `MetricSnapshotV1` is tenant-scoped, immutable, append-only and digest-bound.
- BSON timestamps are normalized to UTC millisecond precision before evidence identity is validated.
- provider raw observations, normalized metrics, unavailable metrics, source version and freshness policy are stored separately.
- explicit provider zero is valid evidence; absent provider data is `UNAVAILABLE`, never fabricated as zero.
- `MEMBERS_REACHED` remains provider-specific evidence and is not falsely normalized as impressions.
- deterministic operation identity binds tenant + publication + provider post identity + collection bucket.
- collection job identity also binds LinkedIn connection generation so stale jobs cannot silently run after reauthorization.
- S11 uses `analytics.linkedin.v1` durable intents and dedicated `pa:analytics:v1` Redis transport.
- only S10 `PUBLISHED` Publication + durable provider receipt can create automatic analytics work.
- provider reads are side-effect-free and classified safe vs retryable.
- S10 publishing capability remains independent from `r_member_postAnalytics` analytics consent.
- existing OAuth callback path is preserved; explicit Analytics enablement upgrades scope through tenant-scoped state.
- automatic lifecycle buckets are `T+1h`, `T+24h`, `T+72h`, `T+7d`; manual capture is also durable/idempotent by minute bucket.
- Analytics overview reports coverage and freshness state instead of hiding partial evidence.
- Analytics UI renders provider-specific unavailable metrics and stale/degraded states explicitly.

## Migration behavior

No historical counter backfill becomes authoritative automatically. Existing S10 publications become eligible for collection only when they have `PUBLISHED` state + provider receipt evidence. Existing LinkedIn connections remain publish-capable even if they lack analytics scope.

## Feature flags

- `MK1_ANALYTICS_WORKER=false` by default.
- `NEXT_PUBLIC_MK1_ANALYTICS=false` by default.
- S9 transport remains prerequisite for automatic collection.
- disabling analytics worker preserves all existing snapshots.

## Observability

Required safe telemetry/evidence: due capture age, attempt outcome, provider status class/latency, rate-limit events, snapshot append count, duplicate operation conflicts, unavailable metrics, latest successful capture age, capability readiness, exact provider API version.

No tokens or provider authorization headers may appear in analytics evidence.

## Failure paths

- missing analytics permission/capability: safe degraded state, no fabricated snapshot;
- read-only 429/5xx/transport failure: bounded retry through S9 execution semantics;
- partial provider observation: persist only actual values + unavailable markers;
- stale connection generation: safe failure, no provider read under superseded identity;
- persistence retry: deterministic operation key prevents duplicate authority;
- Redis restart/loss cannot erase Publication or snapshot Mongo authority.

## Rollback

Set `MK1_ANALYTICS_WORKER=false` and `NEXT_PUBLIC_MK1_ANALYTICS=false`. Historical snapshots remain readable and immutable. Publishing remains independent.

## Risks

Primary: R11, R12, R16.  
Inherited: R09, R13.

## Required tests/certification

Dedicated workflow: `.github/workflows/s11-cert.yml`.

Candidate consensus must include CI + Docker + S3 + S4 + S5 + S6 + S7 + S8 + S9 + S10 + S11 on one exact SHA. Post-merge the same 11-workflow matrix must be green again on the exact resulting `main` SHA.

## Sequence

```text
S11.0 Formalization                              CLOSED
S11.1 MetricSnapshot domain + Mongo repository  IMPLEMENTED
S11.2 Analytics capability + OAuth upgrade      IMPLEMENTED
S11.3 LinkedIn analytics adapter                IMPLEMENTED
S11.4 S9 analytics transport + worker           IMPLEMENTED
S11.5 Collection policy + dispatcher            IMPLEMENTED
S11.6 API/read model                            IMPLEMENTED
S11.7 Analytics UX                              IMPLEMENTED
S11.8 chaos/security/browser certification      READY FOR CANDIDATE
S11.9 exact-SHA premerge                        PENDING
S11.10 merge/postmerge                          PENDING
```

Implementation completion is not certification. S11 remains open until exact-SHA pre- and post-merge consensus both pass.
