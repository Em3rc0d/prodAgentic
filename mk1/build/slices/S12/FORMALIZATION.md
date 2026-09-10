# S12 FORMALIZATION — PerformanceSummary + Planner Learning

Status: **FROZEN FOR IMPLEMENTATION**

Base authority:

`main@4497b41d7c37118a17e257fee2702fcd0172d43b`

S11 Analytics Snapshots is `CERTIFIED/CLOSED` at this authority.

## Objective

Complete MK1 V1 learning with an auditable, confidence-aware `PerformanceSummaryV1` that consumes normalized S11 evidence and can influence BatchPlanner **only as the final tie-breaker among candidates that already satisfy all stronger product constraints**.

Canonical flow:

```text
MetricSnapshotV1 append-only evidence
→ immutable publication/content attribution
→ PerformanceSummaryV1
→ confidence-aware candidate signal
→ BatchPlanner final tie-breaker
```

S12 does not mutate Profile strategy, does not optimize raw engagement, and does not make causal claims from observational metrics.

## Frozen priority law

Planner priority is exactly:

```text
Brand
> Safety
> Novelty
> Diversity
> Quality
> Performance
```

Performance therefore may never:

- admit a candidate blocked by hard novelty/cooldown;
- weaken claim-safety policy;
- replace a more diverse eligible candidate;
- override a stronger novelty verdict;
- turn low-confidence observations into a strong recommendation;
- mutate a Profile/ProfileVersion automatically.

The implementation must preserve this ordering structurally, not only by comments.

## Evidence law

1. S12 consumes `MetricSnapshotV1`, never raw provider payloads.
2. One publication contributes at most one learning observation: the latest mature lifecycle snapshot selected by deterministic policy.
3. V1 mature buckets are `t+7d` first, then `t+72h`. `t+1h`, `t+24h`, and `manual-*` snapshots remain visible analytics evidence but do not drive planner learning.
4. A learning observation requires `views_or_impressions > 0` and all three interaction metrics (`likes_or_reactions`, `comments`, `shares`) to be available. Missing metrics are not coerced to zero.
5. Publication → Approval → ContentItem attribution must be tenant-scoped and derived from immutable authority relationships.
6. Eligible dimensions in V1 are: `role`, `canonical_topic`, `format`, `hook_pattern`, `visual_pattern`, and `platform`.
7. Summary generation is deterministic for the same eligible evidence set and policy version.
8. Every summary binds its exact input snapshot digests through `input_digest` and is persisted immutably/append-only.
9. Mongo is summary authority; no Redis learning state is authoritative.

## Performance signal

For each eligible publication observation:

```text
interaction_rate = (reactions + comments + shares) / impressions
```

The observation is descriptive, not causal.

A bounded observation score is derived deterministically from profile-relative evidence:

- interaction-rate percentile is the primary component;
- impressions percentile is a secondary reach component;
- percentile ranking prevents one viral outlier from dominating by magnitude;
- final observation score is constrained to `[0, 1]`.

V1 weights:

```text
0.70 interaction-rate percentile
0.30 impressions percentile
```

For each `(dimension, key)`, summary signal is the mean observation score minus the profile baseline mean, clipped to `[-1, 1]`.

## Confidence law

Confidence is sample-size bounded:

```text
n < 3      → INSUFFICIENT
3 <= n < 5 → LOW
5 <= n <10 → MEDIUM
n >= 10    → HIGH
```

Planner behavior:

- `INSUFFICIENT` and `LOW` signals are explanatory only and contribute `0` to ranking;
- `MEDIUM` signals contribute at reduced weight;
- `HIGH` signals contribute at full bounded weight;
- no signal may make a blocked candidate eligible.

The summary also records total eligible publication count, evidence window, latest snapshot time, limitations, and dimensions with insufficient evidence.

## Domain contracts

### PerformanceSignalV1

```text
signal_id
dimension
key
sample_size
mean_observation_score
baseline_score
lift
confidence
planner_weight
note
```

### PerformanceSummaryV1

```text
schema_version=1
summary_id
tenant_id
profile_id
policy_version
window_start
window_end
sample_size
eligible_publication_ids[]
input_snapshot_ids[]
input_digest
baseline_score
signals[]
insufficient_dimensions[]
latest_snapshot_at
limitations[]
summary_digest
created_at
```

The model is frozen and digest-validated. Summary documents are append-only; identical input evidence returns the existing deterministic summary.

## Planner integration

`BatchPlannerService` receives a `PlannerPerformanceSourcePort` abstraction. It never queries MetricSnapshots directly.

When `MK1_PLANNER_LEARNING=false`:

- no summary is loaded or built;
- selection behavior remains S2-compatible;
- `PlannerStrategySnapshot.performance_summary_version` remains null.

When enabled:

1. load/build the current `PerformanceSummaryV1` for the Profile;
2. run existing hard novelty gates unchanged;
3. compute the existing diversity/quality tuple unchanged;
4. use bounded performance score **only after that tuple**;
5. persist summary identity/digest in the Batch strategy snapshot;
6. record per-candidate performance contribution in planning trace/evidence.

Candidate performance score is the bounded weighted sum of matching `MEDIUM/HIGH` summary signals for supported dimensions. Missing keys contribute zero; negative evidence may reduce the tie-breaker score but can never block an otherwise eligible candidate.

## API/read surface

S12 adds a tenant-scoped descriptive surface:

```text
GET  /api/analytics/performance-summary?profile_id=...
POST /api/analytics/performance-summary/rebuild?profile_id=...
```

The route exposes no provider secrets/raw token material. Rebuild reads only persisted internal authority and creates/reuses an immutable summary.

## Failure/degradation law

- no mature snapshots → summary reports insufficient evidence; planner behaves as pre-S12;
- incomplete normalized metrics → observation excluded with limitation, never zero-filled;
- broken attribution chain → observation excluded and counted as limitation;
- summary repository unavailable while learning enabled → planner degrades safely to no performance tie-breaker; batch planning itself remains available;
- invalid/corrupt summary digest → reject the summary and do not learn from it.

## Required certification matrix

S12-CERT must prove on one exact candidate SHA:

1. deterministic `PerformanceSummaryV1` identity/digest;
2. latest mature snapshot selection and no double-counting per publication;
3. `UNAVAILABLE != 0` by excluding incomplete observations;
4. confidence thresholds and zero planner weight for insufficient/low evidence;
5. tenant isolation for evidence and summaries;
6. identical input evidence is idempotent/append-only;
7. feature flag OFF preserves S2 selection behavior;
8. hard novelty block cannot be overridden by arbitrarily high performance;
9. diversity/quality tuple outranks performance;
10. performance resolves only an otherwise-equal eligible tie;
11. Batch strategy snapshot binds summary version/digest when learning is active;
12. planning trace records bounded performance evidence without provider payloads;
13. no causal wording or secret leakage in API/evidence;
14. base CI + Docker + S3-S11 regressions remain green.

Expected exact-SHA pre/post matrix becomes **12 workflows**: CI, Docker, S3–S12.

## Implementation sequence

```text
S12.0  Formalization                                      CLOSED BY THIS RECORD
S12.1  PerformanceSummary domain contracts              NEXT
S12.2  Tenant-scoped attribution + Mongo summary repo   LOCKED
S12.3  Deterministic summarizer + confidence policy     LOCKED
S12.4  PlannerPerformanceSource boundary                LOCKED
S12.5  BatchPlanner final tie-breaker integration       LOCKED
S12.6  API/read surface                                  LOCKED
S12.7  Guardrail + degradation tests                    LOCKED
S12.8  S12-CERT exact-SHA workflow                      LOCKED
S12.9  exact-SHA pre-merge consensus                    LOCKED
S12.10 merge + post-merge consensus                     LOCKED
```

## Closeout law

S12 is `CERTIFIED/CLOSED` only after:

1. one immutable candidate SHA passes all 12 pre-merge workflows;
2. merge is pinned to that exact candidate SHA;
3. all 12 applicable workflows pass again on the resulting exact `main` SHA.

Implementation completion is not certification. S12 closure completes MK1 Phase G; Production Cutover remains a separate certified phase.
