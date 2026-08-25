# Design — Content Intelligence

Status: DESIGN BASELINE

## Design principles

1. No heavy onboarding.
2. No hidden learning that changes user identity or voice.
3. Intelligence appears when it is useful in the workflow.
4. Existing approval and publication rules remain authoritative.
5. Warnings should inform without creating unnecessary friction.
6. Blocking behavior is reserved for high-confidence duplicate publication or integrity violations.
7. Every new intelligence result should be inspectable enough to answer "why am I seeing this?".

---

# CI-01 — Semantic Content Memory

## User problem

A user can create a new draft that is textually different from a previous post but expresses substantially the same idea. Exact publication idempotency cannot detect this because the approved bundle is different.

## User-facing behavior

### At idea selection / generation start

prodAgentic may show:

- `No significant overlap found.`
- `Related previous content found.`
- `This idea is very similar to content already published.`

The result includes up to three nearest historical items with:

- title/topic/idea,
- status,
- publication date when available,
- similarity score,
- compact reason/overlap summary when available.

### At review

A durable `memory_check` result is visible in the run detail so the user can inspect what was compared before approval/publication.

### At publication boundary

Rules:

- Same approved bundle already `PUBLISHED`: current idempotent behavior returns existing evidence.
- Exact normalized final-content duplicate of another published run in the same workspace: BLOCK by default.
- Very high semantic overlap with another published run: WARN before approval/publish; do not silently publish.
- Moderate semantic overlap: informational only.

Initial proposed thresholds are dataset-calibrated, not hardcoded product truth. Golden Dataset evaluation decides them.

## User actions

When high overlap is detected:

- `Open previous content`
- `Continue as a new angle`
- `Revise idea`

A future explicit override may require a reason, but v1 does not require an approval bureaucracy around non-exact semantic overlap.

## What it does NOT do

- It does not infer user personality.
- It does not auto-delete drafts.
- It does not automatically rewrite content.
- It does not compare across workspaces.

---

# CI-02 — Source-Grounded ContentRuns

## User problem

Technical/expert content often includes facts, numbers, project details or claims that should come from deliberate source material. Today the research/write pipeline has no durable run-level source contract.

## User-facing behavior

Sources are optional.

A user can create normally with no source attachment.

When sources are useful, the creation flow can accept:

- paste text/note,
- uploaded/external source reference supplied by a connector,
- repository/document excerpt,
- URL snapshot supplied by a source adapter,
- explicit user assertion.

The run displays a small `Sources` section rather than a mandatory onboarding flow.

## Grounding modes

### `OPEN`

Sources are context, but model knowledge may still be used.

### `SOURCE_PREFERRED`

The system should prioritize attached sources for factual/detail claims and avoid introducing unsupported specificity.

### `SOURCE_ONLY`

The research/writing stages must rely only on attached source snapshots plus the user's idea/instruction. If evidence is insufficient, the system should produce a bounded warning rather than inventing specifics.

Default for ordinary use: `OPEN`.

A technical/high-trust workflow may select `SOURCE_PREFERRED` or `SOURCE_ONLY`.

## Source card

Each source shown to the user should expose:

- source label,
- source type,
- authority (`USER_PROVIDED`, `SOURCE_SNAPSHOT`, etc.),
- captured timestamp,
- digest/version identity,
- optional origin reference.

Secrets/tokens are never persisted as source content.

## Approval interaction

Approval freezes the source-set identity used for the final reviewed content by digest/reference. Approval does not need to copy every source byte into the approval object if immutable source snapshots are already persisted; it must freeze a stable source-set digest.

## What it does NOT do in v1

- Claim-by-claim citation UI.
- Automatic browsing of all user accounts.
- Continuous source ingestion.
- Assertion that attached sources are true merely because they are attached.

---

# CI-03 — Visual Intelligence

## User problem

The current visual prompt stage is optimized for striking cinematic metaphor. That produces attractive visuals, but it can choose the wrong communication form for technical posts where a diagram, cutaway, data visual or before/after structure would explain the idea better.

## User-facing behavior

Before rendering, prodAgentic creates a `VisualIntent` record.

Fields visible or inspectable:

- intent class,
- communication goal,
- primary subject,
- required elements,
- avoid elements,
- preferred aspect ratio,
- render style,
- confidence/reason.

Example:

```text
Intent: TECHNICAL_ILLUSTRATION
Goal: Explain corrosion under insulation failure path
Required: pipe cutaway, wet insulation, corroded steel surface, sensor position
Avoid: generic refinery skyline, unrelated machinery, decorative text
```

Then the existing visual prompt generator receives the intent and final post instead of operating on final post alone.

## Intent classes

- `TECHNICAL_DIAGRAM`
- `TECHNICAL_ILLUSTRATION`
- `DATA_VISUALIZATION`
- `BEFORE_AFTER`
- `PRODUCT_HERO`
- `EDITORIAL`
- `CINEMATIC_METAPHOR`
- `NO_VISUAL`

## Fallback behavior

If intent classification fails:

- do not fail text generation,
- mark visual intent as failed/fallback,
- allow existing visual prompt flow or no-visual path according to configuration.

Visual failure remains non-terminal to text content, matching current product behavior.

---

# Shared UX rules

## Content Library

The library remains the durable entry point for prior runs. New intelligence appears as small signals:

- overlap badge,
- source count / grounding mode,
- visual intent,
- publication evidence.

Do not turn the library into a dense analytics dashboard.

## Review page

Review is where intelligence becomes actionable:

- `Related content` signal,
- `Sources` summary,
- `Visual intent` summary,
- existing copy + visual editing,
- explicit approval.

## Progressive complexity

A first-time user should still be able to:

1. type a topic/idea,
2. generate,
3. review,
4. approve,
5. publish.

No source, memory or visual-intent configuration should be mandatory before the first useful output.

## Trust language

Use precise labels:

- `Observed overlap`, not `You always repeat this topic`.
- `Source attached`, not `Fact verified`.
- `Suggested visual intent`, not `Correct visual`.

The product should be confident about stored evidence and cautious about model interpretation.