# PR-UI-01 — Premium frontend system

## Intent

Bring prodAgentic's visual and interaction quality up to the level of the already-working product core without changing content authority, approval, scheduling, OAuth, persistence, or publication behavior.

## Hard boundary

**Frontend only.** No backend route, model, persistence contract, provider integration, worker behavior, approval invariant, or publication authority is changed by this slice.

## Scope

### Global product shell
- Replaces the legacy floating text links with a responsive route-aware product rail.
- Preserves all canonical routes: Create, Library, Profiles, Publish, Schedule.
- Uses a compact desktop rail, expanded wide-desktop rail, and bottom navigation on mobile.
- Adds a restrained system-ready signal and consistent product identity.

### Premium visual system
- Introduces one shared spacing, typography, panel, metric, status, empty-state, input, button, and table language.
- Adds CSS-built 3D ambient scenes with no asset or backend dependency.
- Adds restrained motion for depth, state transitions, orbital scenes and hover response.
- Honors `prefers-reduced-motion`.
- Adds responsive safeguards for multi-column operational layouts.

### Create
- Keeps the existing generation/event-stream logic untouched.
- Elevates the idle hero into a 3D orbital composition.
- Refines tabs, idea cards, pipeline states, forms and preview surfaces.
- Keeps the existing agent pipeline, selected idea, render and diagnostics behavior unchanged.

### Library
- Reframes Content Library as a durable evidence archive.
- Adds summary metrics, local search, status filters, stronger status hierarchy and deliberate empty/loading states.
- Keeps `fetchContentRuns` and all existing ContentRun routes unchanged.

### Profiles
- Reframes Profiles as identity architecture.
- Groups fields into Identity, Audience & Voice, Guardrails, and Generation & Visual Defaults.
- Preserves create/update/default profile calls and every existing profile field.
- Keeps existing ContentRun profile snapshots authoritative and unchanged.

### Publishing
- Reframes LinkedIn Publishing as distribution control.
- Establishes connected identity → approval guardrail → exact publication hierarchy.
- Keeps Connect / Reconnect / Disconnect and `publishContentRun(run_id)` behavior unchanged.
- Keeps token validity and API version as secondary operational metadata.
- Adds the shared 3D publishing scene and premium empty/queue states.

### Scheduling
- Reframes Scheduling as delivery orchestration.
- Adds ready/scheduled/publishing/published summary metrics.
- Preserves exact local-time-to-UTC conversion and existing schedule/cancel calls.
- Keeps worker and backend scheduling semantics untouched.

## Explicit non-goals

This slice does not alter:
- backend code;
- LinkedIn OAuth logic or scopes;
- access-token persistence or encryption;
- PublicationCoordinator;
- approval bundle construction;
- visual byte verification;
- scheduler/worker semantics;
- ContentRun persistence;
- real-publication authorization policy;
- provider/model selection logic.

## UX direction

The target is a restrained premium operations product: strong hierarchy, cinematic depth without visual noise, high trust, clear next actions, and technical evidence available without dominating the primary experience.

The 3D layer is intentionally presentation-only. Product truth remains in the existing backend and persisted evidence contracts.
