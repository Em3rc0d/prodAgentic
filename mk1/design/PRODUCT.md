# MK1 Product Contract

Status: **DESIGN FROZEN**  
Provenance: `GENERATED`, promoted from accepted MK1 thesis.

## Product promise

prodAgentic helps an operator continuously produce trustworthy content for multiple editorial identities without making the operator configure or supervise the internal agent machinery.

The product is opinionated: it remembers, plans, validates, recovers and explains.

## Primary product entities in user language

The UI speaks primarily about:

- **Profile** — an editorial identity.
- **Batch** — a group of content prepared for a target window.
- **Content** — one publishable concept/piece.
- **Review** — the decision surface before approval.
- **Schedule** — when/where approved content should go.
- **Performance** — what happened after publication.

Terms such as `GenerationRun`, consumer group, retry attempt, digest and vector similarity stay outside the default experience.

## Primary navigation

```text
Home
Profiles
Create
Review
Calendar
Analytics
```

`Library` is not a primary V1 navigation item. Historical content is reachable through Review search/history, Profile history, Calendar and Analytics. If future evidence shows a dedicated library is needed, add it through a product ADR.

## Home

Purpose: answer “What is happening and what needs me?”

Home includes:

- active Profile context / fast Profile switcher;
- Ready, Scheduled, Published-today and Needs-attention counts;
- today/upcoming timeline;
- highest-priority review item;
- two or three primary actions only;
- quiet system-health indicator that expands only on degradation.

## Profiles

Purpose: create and maintain editorial identities with minimal form work.

Profiles support:

- quick setup;
- example ingestion;
- inferred identity preview;
- edit of user-meaningful traits;
- version visibility under Advanced;
- platform connections as a separate sub-surface, not part of identity itself.

## Create

Hero action: **Generate next batch**.

Common shortcuts:

- Tomorrow
- This week
- 1 piece
- 4 pieces
- 7 pieces

The user may optionally specify a campaign/goal/topic constraint, but an empty topic box must still allow memory-aware planning when the Profile has sufficient strategy context.

## Review

Purpose: make a high-quality human decision rapidly.

Default view emphasizes:

- visual preview;
- title/hook;
- caption/body;
- CTA/hashtags where applicable;
- format and editorial role;
- status and warnings.

Deep evidence is available through “Why/Details”, not expanded by default.

## Calendar

Purpose: place approved content into time and channel context.

Calendar shows approved unscheduled work, scheduled work, publishing state and completed receipts without exposing queue internals.

## Analytics

Purpose: explain patterns useful for future planning.

Analytics does not encourage blind optimization. It summarizes performance by role, topic, angle, format, hook family, visual pattern, CTA and time when evidence is sufficient.

## Autonomy ladder

MK1 defines explicit autonomy levels:

1. `SUGGEST` — ideas only.
2. `GENERATE` — produce content.
3. `GENERATE_QA` — produce and automatically validate/recover.
4. `GENERATE_QA_SCHEDULE` — schedule only after explicit approval.
5. `POLICY_APPROVAL` — future; approval under user-authored policy.
6. `FULL_AUTOMATION` — future.

**V1 default:** level 3 for production + explicit human approval + user scheduling/publish policy.

## V1 format support

First-class:

- text-only;
- single static image;
- carousel;
- infographic.

Later:

- GIF;
- short video;
- long-form/motion pipelines.

## V1 platform support

- LinkedIn: automatic adapter when connection capability is valid.
- Other channels: capability-aware manual export package until a certified adapter exists.

The UI must never imply an unsupported automatic capability.

## Success metrics

### Experience targets

- time to first useful Profile: target under 5 minutes;
- time from returning user to requested next batch: one primary action plus optional constraints;
- human intervention per routine batch: target 2–4 minutes, dominated by review rather than configuration;
- avoid forced advanced settings on happy path.

### Editorial metrics

- topic/angle collision rate;
- batch diversity score;
- off-brand rejection rate;
- manual edit rate;
- human approval rate;
- safety/claim rejection rate.

### Operational metrics

- generation completion rate;
- QA recovery rate;
- render success;
- publication success;
- reconciliation-required rate;
- asset-integrity failure rate.

### Business metrics

When commercialization begins:

- active Profiles;
- batches prepared per active account;
- approved/scheduled content per week;
- retained active accounts;
- paid conversion and plan utilization.

## Non-negotiable product truth

A green system status cannot mean “the agents ran.” It means the user-relevant outcome is valid: content is ready, approved evidence is intact, schedules are durable, publication receipts are real, or an uncertainty is explicitly surfaced.
