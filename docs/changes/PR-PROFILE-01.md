# PR-PROFILE-01 — Content Profiles

## Product gate

prodAgentic must be able to operate more than one professional identity without turning identity into mutable prompt text scattered across agents.

## Contract

A `ContentProfile` is a versioned reusable configuration containing:

- identity / positioning
- audience
- voice
- core and excluded topics
- target and image-prompt languages
- preferred post length and style
- visual preference
- forbidden claims
- banned phrases
- brand constraints

Exactly one active profile may be marked `is_default=true`.

## Run immutability

When generation begins, the resolved profile is copied into:

- `GenerationContext.content_profile_id`
- `GenerationContext.content_profile_snapshot`
- `ContentRun.content_profile_id`
- `ContentRun.content_profile_snapshot`

The snapshot includes the profile version. Later edits to the reusable profile never rewrite an existing ContentRun.

## Agent propagation

`BaseAgent` appends the frozen profile constraints to every model request. This prevents cross-stage persona drift: Idea, Research, Writer, Editor and Visual receive the same identity and guardrails.

The profile layer explicitly tells agents not to invent evidence, metrics, credentials, customers, results or personal experiences.

## Visual policy

`visual_enabled=false` skips visual-prompt generation for that profile without failing the text pipeline.

## API

- `GET /api/content-profiles`
- `GET /api/content-profiles/{profile_id}`
- `POST /api/content-profiles`
- `PATCH /api/content-profiles/{profile_id}`
- `POST /api/content-profiles/{profile_id}/default`
- `DELETE /api/content-profiles/{profile_id}` archives rather than destroying history

Generation endpoints accept optional `content_profile_id`; when omitted, the active default profile is resolved automatically.

## Frontend

`/profiles` provides:

- profile library
- create/edit
- version visibility
- default selection
- identity, audience, voice, topic and guardrail editing
- language / visual defaults

## Acceptance

1. A default profile is automatically applied to new generation runs.
2. An explicit active profile can override the default.
3. A missing explicit profile returns an error rather than silently falling back.
4. Every new ContentRun stores the exact profile version used.
5. Editing a reusable profile does not change historical run snapshots.
6. Agent requests contain the frozen profile constraints.
7. Visual generation can be disabled by profile without making text generation fail.
8. Backend tests, frontend tests, lint, compile and Next build must be green before merge.
