# MK1 Calendar and Analytics

Status: **FROZEN FOR V1**

# Calendar

## Purpose

Calendar unifies approved content placement, schedule status and publication outcome.

It replaces the need for separate primary “Scheduling” and “Publishing” navigation.

## Views

- Week (default)
- Month
- Queue/list

## Content states

Visually distinct using label + icon + color:

- Approved / Unscheduled
- Scheduled
- Publishing
- Published
- Needs reconciliation
- Failed safely
- Cancelled

## Scheduling interaction

Drag/drop may be added only if it preserves exact timezone semantics and accessibility. The baseline interaction is an explicit schedule dialog showing:

- Profile/channel;
- local date/time;
- timezone;
- approved content identity;
- capability status.

## Unsupported channel

Calendar can still hold a manual publishing intention, but must label it as manual and provide export package/action rather than pretending an automatic worker exists.

## Reconciliation

`Needs reconciliation` is a first-class trust state. It receives a visible warning and no automatic “retry” button until reconciliation logic determines the safe next action.

# Analytics

## Purpose

Analytics produces evidence useful for planning, not a dopamine dashboard.

## V1 sections

### Overview

- published content count;
- normalized available impressions/views;
- interactions available from connected providers;
- data freshness timestamp.

### Content patterns

Where sample size permits, group by:

- editorial role;
- canonical topic;
- angle;
- format;
- hook family;
- visual pattern;
- CTA family;
- schedule window.

### Profile learning summary

Show bounded statements such as:

> “Across 8 comparable posts, diagram-led explainers received stronger save/share signals than photo overlays.”

Always indicate insufficient evidence when the sample is weak.

## Learning guardrail

The Planner receives summarized features, confidence and windowed history — never an instruction to blindly repeat the highest metric.

Priority order remains:

```text
Brand
Safety
Novelty
Diversity
Quality
Performance
```

## Data freshness

Each metric surface displays last successful provider sync time. Missing/partial metrics are represented as unavailable, not zero.
