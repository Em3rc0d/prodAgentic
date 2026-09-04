# MK1 Profile Setup

Status: **FROZEN**

## Design objective

Internally a Profile may contain rich identity, editorial, novelty, claims, visual and publishing policy. Externally the default setup must feel closer to teaching a capable assistant than filling an enterprise configuration form.

## Quick setup

### Step 1 — Identity

Fields:

- `What is this Profile called?`
- account type chip: Personal brand / Business / Education / Niche / Other.

### Step 2 — Goal

Multi-select:

- Grow
- Educate
- Build authority
- Sell
- Build community
- Entertain

### Step 3 — Audience

Natural-language field with suggested chips.

Example:

```text
drivers who want to care for used cars
```

The system may extract reusable audience segments but shows plain-language output.

### Step 4 — Voice

Selectable descriptors:

- Direct
- Professional
- Close
- Technical
- Simple
- Humorous

Allow a short free-text nuance but do not require it.

### Step 5 — Production preference

Primary question:

> How much content do you usually want prepared at once?

Choices: 1 / 4 / 7 / Custom.

This sets a default, not a permanent constraint.

### Step 6 — Channels

Capabilities shown by user meaning:

- LinkedIn
- Instagram
- TikTok
- Manual export

Connecting an OAuth account is separate from selecting an editorial channel preference.

### Step 7 — Teach your style (optional, high value)

Accept:

- pasted captions;
- uploaded previous visuals/assets;
- bio/about text;
- links/imports where supported later.

Always provide Skip.

## Inference

Examples pass through a Profile Analyzer that proposes:

```text
identity summary
audience segments
voice traits
topic families
excluded/avoid topics
hook tendencies
caption length tendency
format tendencies
visual traits
CTA style
claim/safety sensitivities where inferable
```

Inference output is a proposal, not hidden truth.

The user receives:

> “This is what I understood.”

Actions:

- Looks good
- Edit

## Advanced profile editor

Progressively disclosed sections:

```text
Identity
Editorial strategy
Memory & novelty
Copy rules
Claims & safety
Visual system
Publishing preferences
Advanced agent policy
```

The default user should rarely need the last four sections.

## Versioning behavior

Every accepted Profile update creates a new version/snapshot identity.

Historical Batches/GenerationRuns continue to reference the version used at creation.

The UI may show “Profile v12” under Advanced history, but routine screens should say only that historical content preserves its original Profile settings.

## Connection separation

A Profile is editorial identity, not an OAuth credential.

Connections are tenant-owned resources that can be associated with a Profile/channel distribution target. Secrets never enter Profile snapshots.

## Safe inference limits

The analyzer must not invent:

- personal experiences;
- credentials;
- customers;
- results/metrics;
- regulated claims;
- facts not present in examples or explicitly supplied.

Uncertain inferred traits are marked as suggestions and omitted from strict policy until accepted.
