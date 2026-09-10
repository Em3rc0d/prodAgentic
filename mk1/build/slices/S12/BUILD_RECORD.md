# S12 BUILD RECORD — PerformanceSummary + Planner Learning

Status: **IMPLEMENTATION COMPLETE / EXACT-SHA CERTIFICATION PENDING**

Base authority: `main@4497b41d7c37118a17e257fee2702fcd0172d43b`
Formalization authority: `9f393bb6eb3f31d03010b9011e3cf83dc2b7a3dc`

## Objective

Implement immutable `PerformanceSummaryV1` evidence and a confidence-aware Planner tie-breaker without weakening Brand, Safety, Novelty, Diversity or Quality gates.

## Accepted dependencies

- `mk1/arch/ANALYTICS_LEARNING.md`
- `mk1/plan/VERTICAL_SLICES.md`
- S2 BatchPlanner + NoveltyEngine
- S7 ApprovalBundleV2
- S10 PublicationV1
- S11 MetricSnapshotV1
- `MK1_PLANNER_LEARNING` feature flag

## Implemented runtime surface

```text
backend/domain/learning/{__init__.py,models.py,ports.py}
backend/application/learning/{__init__.py,service.py}
backend/infrastructure/mongo/learning.py
backend/application/planning/service.py
backend/domain/planning/models.py
backend/domain/planning/trace.py
backend/routes/batches.py
backend/routes/analytics_v1.py
backend/tests/test_s12_learning.py
.github/workflows/s12-cert.yml
```

## Authority boundaries

- MetricSnapshotV1 remains append-only measurement authority.
- PerformanceSummaryV1 is append-only derived evidence, not provider authority.
- Planner consumes only PerformanceSummaryV1 via a port; it never reads provider payloads or MetricSnapshots directly.
- Profile/ProfileVersion is never mutated by S12.
- Performance is the final ranking component only after existing hard novelty and diversity/quality ordering.

## Evidence eligibility

- mature buckets only: `t+7d`, then `t+72h` fallback;
- one observation maximum per Publication;
- impressions must be positive;
- reactions/comments/shares must all be available;
- missing normalized evidence excludes the observation instead of fabricating zero;
- tenant-scoped attribution: Publication → Approval → ContentItem → Profile.

## Scoring / confidence

Observation score is profile-relative and bounded:

```text
0.70 * interaction-rate percentile
+ 0.30 * impressions percentile
```

Dimension/key lift is mean observation score minus profile baseline.

Planner weights:

```text
INSUFFICIENT (<3) = 0.0
LOW (3-4)         = 0.0
MEDIUM (5-9)      = 0.5
HIGH (>=10)       = 1.0
```

No causal claim is made; API/summary evidence explicitly says observational association.

## Feature flag / rollback

`MK1_PLANNER_LEARNING` defaults off. When disabled, no summary is loaded/built and S2 ordering remains unchanged.

Rollback: set `MK1_PLANNER_LEARNING=false`. Existing immutable summaries remain inert evidence; no data migration is required.

## Persistence

New collection: `performance_summaries_v1`.

Indexes:

- unique `(tenant_id, summary_id)`;
- unique `(tenant_id, profile_id, input_digest, policy_version)`;
- query `(tenant_id, profile_id, created_at desc)`.

Summary persistence is append-only/idempotent by deterministic input identity.

## Failure/degradation

- insufficient/incomplete evidence → zero planner contribution;
- summary build/read failure → Planner degrades to no learning, never blocks batch creation;
- corrupt summary digest → rejected;
- attribution mismatch/cross-tenant data → excluded;
- no zero-coercion for unavailable metrics.

## Certification

S12-CERT compiles the new surface, runs dedicated S12 tests, reruns the S2 planner suite with learning disabled, and statically proves priority/authority boundaries. Full candidate certification additionally requires CI + Docker + S3–S12 on the same SHA pre-merge and post-merge.
