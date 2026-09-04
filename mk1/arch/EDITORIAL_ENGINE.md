# MK1 Editorial Memory, Novelty and Batch Planning

Status: **FROZEN ARCHITECTURE; thresholds remain calibratable policy**

## Objective

The editorial engine prevents prodAgentic from behaving like a stateless prompt generator. It maintains a compact, queryable representation of what the audience has recently seen or is already committed to see, then uses that evidence to plan a diverse Batch.

# Editorial Memory

## Eligible lifecycle sources

Default V1 memory input:

| Source | Default weight | Rationale |
|---|---:|---|
| `PUBLISHED` | 1.0 | audience definitely consumed/was offered the concept |
| `PUBLISHING` | 1.0 | treat as committed because status may already be public |
| `SCHEDULED` | 1.0 | committed future content; prevent collision before publication |
| `APPROVED` | 1.0 | committed editorial decision even if unscheduled |
| `READY_FOR_REVIEW` | 0.6 | soft collision signal to avoid generating duplicate review work |
| `PLANNED/PRODUCING` same Batch | 1.0 intra-batch | prevents candidates from duplicating each other |
| `REJECTED` | 0 by default | may be kept in audit but not audience memory |

Profiles may adjust soft-memory behavior but cannot ignore published/scheduled content without explicit advanced policy.

## Normalized memory dimensions

```text
canonical_topic
subtopics
angle
hook_pattern
role
format
visual_pattern
entities
semantic_fingerprint
```

The engine compares concepts across these dimensions rather than relying on title-string equality.

# Novelty Engine

## Evaluation layers

### L1 — canonical taxonomy

Maps lexical variants and language variants to stable topic concepts where possible.

Example:

```text
tires / tyres / llantas / neumáticos -> automotive.tires
```

Taxonomy is Profile/domain-extensible and versioned.

### L2 — aliases/lexical overlap

Detects near-identical phrasing, entity combinations and known synonyms cheaply.

### L3 — semantic similarity

Uses embeddings or equivalent semantic representation to detect concept overlap not captured lexically.

Embedding thresholds are configuration/calibration, not hard-coded architectural constants.

### L4 — angle classification

Examples:

```text
diagnosis
maintenance
how_it_works
safety
myth
comparison
story
opinion
checklist
```

Same topic + genuinely different angle may pass after cooldown when policy allows.

### L5 — creative-pattern similarity

Tracks repeated mechanics such as:

- “3 signs…”;
- A/B/C checklist;
- myth vs fact;
- diagram flow;
- before/after;
- personal realization story.

### L6 — visual-pattern similarity

Avoids every Batch becoming the same visual composition even when topics differ.

### L7 — current-batch collision

Candidates are compared against already-selected candidates before final commitment.

## Default cooldown bands

Initial policy:

```text
0–2 days  HARD_COOLDOWN
3–6 days  STRONG_COOLDOWN
7+ days   eligible only when angle/creative treatment is genuinely fresh
```

These are product defaults, not universal truths. Quarry calibration may produce Profile-specific policies without changing the engine contract.

## Novelty result contract

```text
PASS
PASS_WITH_WARNING
REWRITE_ANGLE
REPLACE_TOPIC
BLOCKED
```

Explanation fields include matched content IDs, overlap categories and cooldown reasoning.

# Batch Planner

The planner answers **what composition the Batch needs** before production.

## Inputs

- ProfileVersion;
- target window and requested size;
- request constraints;
- recent memory window;
- current scheduled/approved commitments;
- normalized PerformanceSummary when enough evidence exists;
- planner policy version.

## Role strategy

Profiles define preferred role families, e.g.:

```text
Content Seller: relatable / education / personal_story / community
Logan: symptom / safety / mechanical_explainer / maintenance
Tech: technical_learning / humor / system_design / tradeoff
```

These are examples of Profile policy, not hard-coded product-wide roles.

## Candidate pool

Default target pool:

```text
max(8, requested_size * 3)
```

with a V1 safety cap configurable by plan/cost policy (recommended initial cap: 24).

The planner may generate additional candidates only within a bounded recovery budget if hard gates eliminate too many.

## Selection order

Selection is intentionally policy/constraint-driven rather than an unexplained single magic score:

1. remove forbidden/excluded/hard-cooldown candidates;
2. satisfy required editorial role coverage where possible;
3. prefer stronger novelty bands;
4. prefer Profile fit;
5. maximize intra-batch angle/creative/visual diversity;
6. prefer research/claim feasibility;
7. use PerformanceSummary as a bounded tie-breaker, never a hard override.

A greedy constrained selector is acceptable V1. More sophisticated optimization must prove value against the golden datasets before replacement.

## Insufficient fresh candidates

The system may return fewer items than requested rather than silently lowering hard novelty/safety policy.

The Batch records requested vs selected size and reason.

## Explainability

User explanation is concise; operations evidence is rich.

User:

> “This angle was replaced because it was too close to a post from four days ago.”

Advanced:

```text
matched content
canonical topic overlap
angle overlap
hook/creative overlap
cooldown band
policy version
```
