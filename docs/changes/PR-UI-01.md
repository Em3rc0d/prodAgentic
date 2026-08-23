# PR-UI-01 — Professional workspace polish

## Intent

Improve perceived product quality without changing content authority, approval, scheduling, OAuth, or publication behavior.

## Scope

### Product navigation
- Replaces the legacy floating text links with a responsive product dock.
- Uses route-aware active state and accessible `aria-current` semantics.
- Keeps all canonical routes unchanged: Create, Library, Profiles, Publish, Schedule.
- Collapses to icon navigation on narrow screens.

### LinkedIn Publishing
- Reframes the page from a provider/configuration console into a distribution-control workspace.
- Establishes a clear hierarchy: connected identity → approval guardrail → publication queue.
- Shows token validity and API contract as secondary operational metadata instead of primary content.
- Shows connection, approval and publication as a three-step controlled path.
- Adds a deliberate empty state with clear next actions when the LinkedIn account is connected but no approved ContentRuns exist.
- Preserves Connect / Reconnect / Disconnect and exact ContentRun publication behavior.
- Preserves immutable approval evidence and publication receipts.

## Explicit non-goals

This slice does not alter:
- LinkedIn OAuth logic or scopes;
- access-token persistence;
- PublicationCoordinator;
- approval bundle construction;
- visual byte verification;
- scheduling semantics;
- ContentRun persistence;
- real-publication authorization policy.

## UX direction

The target is a restrained professional operations product: high information hierarchy, low chrome, no developer-console language in primary surfaces, and technical evidence available without dominating the experience.

Library, Profiles and Scheduling retain their current functional layouts in this PR. Their visual restyle should follow only after this direction passes browser review, avoiding a broad visual rewrite before the product language is validated.
