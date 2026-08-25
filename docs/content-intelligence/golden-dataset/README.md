# Golden Dataset — Content Intelligence

Status: BASELINE v0.1

## Purpose

Provide stable product-level fixtures that prevent us from declaring intelligence correct simply because code runs.

The dataset is intentionally small, explainable and adversarial. It is not a training dataset.

## Dimensions

### Memory

Tests whether the system distinguishes:

- exact duplicate,
- normalized duplicate,
- paraphrase duplicate,
- strongly related continuation/new angle,
- same broad topic but different thesis,
- unrelated content.

### Grounding

Tests whether the system distinguishes:

- sufficient source support,
- insufficient evidence,
- conflict between requested claim and source,
- OPEN vs SOURCE_ONLY behavior,
- source-set identity changes.

### Visual intent

Tests whether the system selects communication form rather than defaulting to cinematic artwork.

## Case format

Each case in `cases.json` contains:

- `id`
- `dimension`
- inputs
- expected product outcome
- rationale
- optional minimum/maximum similarity class rather than a brittle exact floating score.

## Evaluation rules

### Memory outcomes

- `EXACT_DUPLICATE`
- `HIGH_OVERLAP`
- `RELATED_NEW_ANGLE`
- `DISTINCT`
- `UNKNOWN_DEGRADED`

Exact duplicate is deterministic and must not depend on an embedding provider.

Semantic thresholds must be calibrated so that all cases meet their expected class. The dataset does not mandate one embedding model.

### Grounding outcomes

- `SUPPORTED`
- `INSUFFICIENT`
- `CONFLICT`
- `OPEN_ALLOWED`

`SOURCE_ONLY` must never silently change to `OPEN_ALLOWED` because a provider/context is weak.

### Visual outcomes

Expected intent class must match the case.

A secondary list of allowed alternatives may exist for genuinely ambiguous cases, but core technical cases should be strict.

## Change control

A failing Golden Dataset case is not fixed by changing the expected answer just to make CI green.

Changing a case requires:

1. documented rationale,
2. explanation of product behavior change,
3. review of whether the previous expectation was wrong or the implementation regressed.

## Dataset growth

Add cases from real prodAgentic usage only when they expose a meaningful product distinction.

Do not flood the dataset with near-identical examples.

Target before first Content Intelligence merge:

- >= 8 memory cases,
- >= 6 grounding cases,
- >= 8 visual-intent cases,
- at least 3 adversarial/boundary cases.