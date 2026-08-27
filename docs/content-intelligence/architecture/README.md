# Architecture — Content Intelligence

Status: ARCHITECTURE BASELINE

## Architectural intent

Extend the existing `ContentRun` lifecycle with bounded, workspace-scoped intelligence while preserving the current release architecture.

No persistent per-user agent is introduced.
No customer-dedicated model instance is introduced.
No customer-dedicated vector database is introduced.

## Existing trusted boundaries to preserve

- `PipelineOrchestrator` owns generation stage orchestration.
- `ContentRunRepository` owns durable generation-stage persistence.
- `ContentRun` is the authoritative lifecycle aggregate.
- `/content-runs/{run_id}/approve` freezes the publishable bundle.
- `PublicationCoordinator` is the only publication lifecycle.
- scheduler invokes the same `PublicationCoordinator` as manual publishing.
- visual bytes remain locally owned and digest-verified before publication.

## New bounded components

```text
                    USER REQUEST
                         │
                         ▼
                Creation / Review API
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Memory Service   Source Service   Visual Intent
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  PipelineOrchestrator
                         │
                         ▼
                    ContentRun
                         │
                         ▼
                 Review / Approval
                         │
                         ▼
               PublicationCoordinator
```

These services are request-scoped/stateless service objects over persisted Mongo data and external model/provider calls where required.

---

# Tenant / workspace isolation

The current codebase is effectively single-workspace at the persisted-content level. Before claiming SaaS-scale semantic memory, all new persisted intelligence records MUST carry `workspace_id` and every lookup MUST include it.

The program should introduce workspace scope in a backward-compatible manner rather than pretend global collections are multi-tenant safe.

Initial migration rule:

- existing records without `workspace_id` are interpreted only inside a configured/default legacy workspace,
- new production multi-tenant paths must always populate an explicit `workspace_id`,
- no semantic lookup is allowed without a resolved workspace scope.

This is a release/security gate, not an optional optimization.

---

# CI-01 — Semantic Content Memory architecture

## Data model

Recommended collection: `content_memory`

One record per durable content item/representation:

```json
{
  "memory_id": "uuid",
  "workspace_id": "workspace",
  "run_id": "run",
  "kind": "IDEA|FINAL_CONTENT|PUBLISHED_CONTENT",
  "normalized_sha256": "...",
  "text_preview": "bounded preview",
  "embedding_model": "provider/model/version",
  "embedding_dimensions": 0,
  "embedding": [],
  "content_status": "READY_FOR_REVIEW|APPROVED|PUBLISHED",
  "external_post_urn": null,
  "created_at": "...",
  "updated_at": "..."
}
```

`embedding` may be absent if the embedding provider is unavailable. Exact normalized hashing remains usable independently.

## Indexing strategy

Minimum indexes:

- unique `(workspace_id, run_id, kind)`
- `(workspace_id, normalized_sha256)`
- `(workspace_id, content_status, created_at)`

Vector/search indexing is implementation-dependent and must not require one index per user. If Mongo deployment capabilities are insufficient, v1 may use bounded candidate retrieval plus application-side cosine similarity for a limited recent/history set. Scale testing decides when a native vector index is necessary.

## Compute model

Embedding creation occurs only when a memory representation is created or materially changes:

- idea accepted/run created,
- final content becomes reviewable,
- publication completes.

Similarity lookup occurs only on explicit creation/review/publication checks.

No idle polling.

## Exact duplicate detection

Always available without embeddings:

1. Unicode normalize.
2. normalize whitespace.
3. preserve semantic punctuation minimally or remove according to canonicalizer version.
4. casefold when appropriate.
5. SHA-256 canonical text.

Store canonicalizer version so future changes remain explainable.

## Semantic duplicate detection

Provider abstraction:

```text
EmbeddingProvider.embed(text) -> EmbeddingResult
```

The provider is shared across workspaces and selected by configuration.

Similarity result:

```json
{
  "candidate_run_id": "...",
  "score": 0.91,
  "kind": "PUBLISHED_CONTENT",
  "published_at": "...",
  "external_post_urn": "..."
}
```

Threshold policy belongs in configuration/dataset calibration, not inside provider code.

## Failure contract

- Embedding provider unavailable: exact duplicate checks remain active; semantic check records `DEGRADED`.
- Memory persistence unavailable: generation may continue, but approval/publish UI must not claim semantic memory succeeded.
- Exact published duplicate found: publication boundary may block.
- Semantic service timeout: never transform uncertainty into `NO_OVERLAP`; return `UNKNOWN/DEGRADED`.

---

# CI-02 — Source Grounding architecture

## Data model

Recommended collection: `content_sources`

```json
{
  "source_id": "uuid",
  "workspace_id": "workspace",
  "run_id": "run",
  "source_type": "PASTED_TEXT|DOCUMENT_EXCERPT|REPOSITORY_EXCERPT|URL_SNAPSHOT|USER_ASSERTION",
  "authority": "USER_PROVIDED|SOURCE_SNAPSHOT|SYSTEM_DERIVED",
  "label": "...",
  "origin_ref": "optional stable ref",
  "content": "bounded source snapshot",
  "content_sha256": "...",
  "captured_at": "...",
  "metadata": {}
}
```

Do not persist connector access tokens, cookies or transient authorization material.

## ContentRun additions

```json
{
  "grounding": {
    "mode": "OPEN|SOURCE_PREFERRED|SOURCE_ONLY",
    "source_ids": ["..."],
    "source_set_sha256": "...",
    "status": "READY|DEGRADED|INSUFFICIENT"
  }
}
```

The run stores IDs + source-set identity. Full source content lives behind the source boundary.

## Pipeline integration

The research stage is the primary insertion point.

```text
idea + topic + profile
        │
        ▼
resolve grounding sources
        │
        ▼
ResearchAgent prompt/context
        │
        ▼
Writer
        │
        ▼
Editor
```

`SOURCE_ONLY` requires prompts/validators to state that unsupported specifics must not be introduced. It is not sufficient to merely prepend sources to a prompt.

## Approval freeze

Approval gains:

- `grounding_mode`
- `source_set_sha256`

This binds the reviewed publishable content to the source set in effect at approval time without copying all source bytes into the approval bundle.

Changing source membership after approval does not mutate the approved bundle. A new reviewed revision would be required to approve against a different source set.

## Failure contract

- Source not found or digest mismatch: `SOURCE_ONLY` cannot silently continue as open generation.
- Oversized source set: use deterministic bounded selection/chunking and record what was actually used.
- Source adapter unavailable: existing persisted snapshot remains usable if integrity matches.

---

# CI-03 — Visual Intelligence architecture

## Data model

Add to `ContentRun`:

```json
{
  "visual_intent": {
    "intent_id": "uuid",
    "class": "TECHNICAL_DIAGRAM",
    "communication_goal": "...",
    "primary_subject": "...",
    "required_elements": ["..."],
    "avoid_elements": ["..."],
    "preferred_aspect_ratio": "16:9",
    "recommended_style": "...",
    "reason": "...",
    "confidence": 0.0,
    "model": "...",
    "created_at": "..."
  }
}
```

## Pipeline integration

Current:

```text
final post -> VisualAgent -> prompt -> render
```

Target:

```text
final post
   ↓
VisualIntentService
   ↓
VisualIntent
   ↓
VisualAgent(final post + intent)
   ↓
prompt
   ↓
existing VisualRenderService
```

The render service, artifact persistence, byte digest and approval rules remain unchanged.

## Deterministic fallback

If intent service fails:

- mark intent status degraded,
- optionally use `CINEMATIC_METAPHOR` fallback only when allowed by profile,
- never fail the text run solely due to visual intelligence.

---

# ContentRun evolution

Avoid turning `ContentRun` into an unbounded document.

Recommended additions are compact snapshots/references:

- `workspace_id`
- `memory_check`
- `grounding`
- `visual_intent`

Large source content and large vector data live in dedicated collections.

## Proposed lifecycle invariants

Existing lifecycle states remain unchanged.

Memory/grounding/visual-intent are evidence dimensions, not new top-level statuses.

This avoids state explosion such as `GROUNDING_READY`, `MEMORY_CHECKED`, etc.

---

# Scaling model

At 1000 users/workspaces:

```text
requests/schedules
       ↓
shared API pool
       ↓
shared job queue / worker pool when async work is needed
       ↓
Mongo collections partitioned logically by workspace_id
       ↓
shared model/embedding provider
```

There is never:

```text
1000 users -> 1000 persistent agents
```

Target idle behavior:

- no generation compute,
- no embedding compute,
- no visual compute,
- no analytics polling,
- only the existing scheduler loop for explicitly scheduled publication work.

---

# Cost controls

- Maximum source bytes/tokens per run.
- Maximum memory candidates per similarity check.
- Embeddings generated once per representation version and reused.
- Similarity checks can prefer `PUBLISHED_CONTENT` and recent relevant history before expanding search.
- Visual intent is computed once per final-content revision unless the user explicitly recomputes it.
- Provider failures degrade features; they do not trigger unbounded retries.

---

# Security and integrity

- All new lookups require workspace scoping.
- Source origin secrets are never persisted.
- Source content size/type validation is mandatory.
- External URLs are not automatically fetched by arbitrary backend code without an explicit safe adapter.
- Memory similarity is advisory except exact duplicate/integrity rules.
- Approval and publication continue to use immutable digests.
- New intelligence must never read mutable draft fields after approval to decide what bytes/text are published.

---

# Migration strategy

1. Add optional fields and collections; no destructive migration.
2. Legacy runs remain readable.
3. Intelligence backfill is optional/on-demand.
4. Published historical runs can be indexed into Content Memory in a bounded explicit migration job.
5. Never block current release startup because intelligence collections are empty.

---

# Architecture gate

Code construction is allowed only after:

- Golden Dataset cases exist.
- Workspace scoping path is decided for the current single-user baseline.
- Embedding provider strategy is implemented behind an interface or semantic memory starts in degraded/exact-only mode.
- Existing approval/schedule/publication tests are explicitly included as non-regression gates.