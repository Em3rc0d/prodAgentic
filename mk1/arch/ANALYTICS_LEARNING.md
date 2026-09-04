# MK1 Analytics and Learning Architecture

Status: **FROZEN V1**

## Data model

Provider metrics are collected as append-only `MetricSnapshot` observations.

Do not update one mutable `likes/impressions/comments` field forever; snapshots preserve time and provider semantics.

## Collection

Analytics worker inputs:

- Publication identity/receipt;
- Connection capability;
- provider rate-limit/freshness policy.

Output:

- raw available provider metrics in a bounded schema;
- normalized metrics where semantic mapping is defensible;
- unavailable fields explicitly absent/null;
- observation timestamp and source version.

## Normalization

Common normalized concepts may include:

```text
views_or_impressions
likes_or_reactions
comments
shares
saves
clicks
watch_time
completion_rate
follower_delta
```

A provider field is mapped only when semantics are sufficiently comparable. Do not force incompatible metrics into fake equivalence.

## Attribution dimensions

Metric analysis can join publication back to immutable content metadata:

- Profile;
- role;
- canonical topic;
- angle;
- format;
- hook pattern;
- visual pattern;
- CTA family;
- schedule window;
- platform.

## PerformanceSummary

A summarizer builds bounded features for BatchPlanner. It records:

- sample size;
- window;
- feature dimension/key;
- normalized signal if meaningful;
- confidence;
- note/limitations;
- insufficient-evidence dimensions.

The Planner consumes this summary, not raw provider payloads.

## Guardrails

Priority order:

```text
Brand
Safety
Novelty
Diversity
Quality
Performance
```

High performance never grants permission to:

- repeat a topic inside hard cooldown;
- reuse the same creative mechanic continuously;
- violate claim policy;
- become off-brand;
- overfit tiny samples.

## Causality

Analytics surfaces observations/correlations. It may claim causal effects only when a controlled experiment or defensible causal design exists.

## Freshness

Each UI summary includes latest successful collection time. Provider failures do not zero metrics; they mark freshness/degradation.

## Later learning

Future experiments may adapt role/format priors, but any automated strategy mutation must be versioned as a Profile/strategy policy change and remain auditable.
