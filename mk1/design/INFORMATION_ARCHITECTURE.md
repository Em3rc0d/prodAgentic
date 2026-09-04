# MK1 Information Architecture

Status: **FROZEN FOR V1**

## Navigation model

```text
Home            /home
Profiles        /profiles
Create          /create
Review          /review
Calendar        /calendar
Analytics       /analytics
```

Secondary/global surfaces:

```text
Settings        /settings
Connections     /settings/connections
Diagnostics     /settings/diagnostics   (advanced/ops-capable accounts only)
Help            contextual
```

## Why the MK0 navigation changes

MK0 exposes implementation-era surfaces such as Library, Publishing and Scheduling. MK1 groups those responsibilities around user jobs:

- historical/reviewable work belongs under Review and contextual history;
- scheduling/publishing placement belongs under Calendar;
- publication evidence appears on content details and Calendar;
- raw system internals belong under Diagnostics.

## App shell

### Desktop

- persistent compact left rail;
- Profile switcher at top of rail;
- primary navigation below;
- account/system status at bottom;
- page header contains context, not duplicate navigation.

### Tablet

- collapsible rail;
- Profile switcher remains one interaction away;
- review preview preserves maximum width.

### Mobile

- bottom navigation for Home/Create/Review/Calendar;
- Profiles and Analytics through “More” or header menu;
- review actions remain sticky and reachable;
- no desktop table is simply squeezed into a phone viewport.

## URL/state rules

- `profile_id` may be represented in app context but should not make every route unreadable.
- direct links to a specific Batch, ContentItem, approval or publication receipt must be stable and reopenable.
- filters/search belong in URL query state when users may share/reload the view.
- generation progress survives navigation/reload through persisted application state; the browser is not the source of truth.

## Content detail ownership

A ContentItem detail view is a contextual route reachable from Review, Calendar or Analytics. It must not duplicate separate “publishing detail” pages.

It can show tabs/sections:

```text
Content
Visual
History
Evidence (Advanced)
Performance (when published)
```

## Empty-state contract

Empty states must teach the next action:

- no Profiles -> create first Profile;
- no Review items -> generate a batch or show next scheduled work;
- no Calendar items -> approve content first;
- no Analytics -> explain that metrics appear after publication.

## Notification hierarchy

Only user-actionable or trust-relevant states enter the main UI:

1. publication uncertainty/reconciliation;
2. approval-blocking QA issue;
3. schedule/publish failure;
4. content needing review;
5. informational completed work.

Provider/model retries that recovered automatically remain in Advanced diagnostics.
