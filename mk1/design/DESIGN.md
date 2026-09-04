# prodAgentic MK1 Design System

Status: **DESIGN FROZEN FOR INITIAL BUILD**  
Design language: **Precision Telemetry**  
Provenance: `GENERATED`, `INSPIRED` by high-performance control environments; no literal motorsport UI copying.

## Intent

The product should feel precise, fast and trustworthy: a premium machine with significant intelligence underneath a calm surface.

The Formula-1 metaphor is behavioral, not decorative:

- user = driver;
- orchestration = pit wall;
- agents = specialist pit crew;
- guards = sensors;
- diagnostics = telemetry;
- fallbacks/recovery = pit procedures.

No checkered flags, fake dashboards, steering wheels, racing stripes, or gratuitous speed imagery are part of the visual language.

## Visual principles

1. **Calm surface, high information integrity.**
2. **One dominant action per operational context.**
3. **Status is structural, not decorative.**
4. **Telemetry is available without becoming noise.**
5. **Content gets the largest visual area; chrome stays compact.**
6. **Avoid generic SaaS gradient-card aesthetics.**
7. **Motion confirms transitions; it never delays work.**

## Core color tokens

Initial MK1 tokens are frozen for implementation and must later be visually regression-tested.

```css
--pa-canvas:        #0B0D10;
--pa-surface-1:     #11151A;
--pa-surface-2:     #171C22;
--pa-surface-3:     #1D242C;
--pa-line:          #29323D;
--pa-line-subtle:   #1D252E;

--pa-text-1:        #F4F7FA;
--pa-text-2:        #A5AFBC;
--pa-text-3:        #727E8C;

--pa-signal:        #D8FF45;
--pa-on-signal:     #111407;
--pa-info:          #6AAEFF;
--pa-success:       #66D19E;
--pa-warning:       #FFB45C;
--pa-danger:        #FF7070;
```

Rules:

- `signal` is brand/action emphasis, not the universal success color;
- status always includes text/icon, never color only;
- long-form reading surfaces may use a high-contrast light content canvas inside the dark shell when previewing real platform content, but application controls retain semantic tokens.

## Typography

Roles:

- Product/UI: `Geist Sans`, fallback `Inter, ui-sans-serif, system-ui`.
- IDs, timestamps, digests, compact telemetry: `Geist Mono`, fallback `ui-monospace, SFMono-Regular, monospace`.

Scale:

```text
Display      32/38, 600
H1           24/30, 600
H2           18/24, 600
Body         14/21, 400
Body strong  14/21, 600
Small        12/18, 500
Telemetry    11/16, 500 mono
```

Avoid oversized marketing typography inside the authenticated product.

## Spacing and geometry

4px base unit.

```text
4, 8, 12, 16, 20, 24, 32, 40, 48
```

Radii:

```text
control 8px
card 12px
panel 16px
pill 999px only for chips/status
```

Avoid every surface becoming a floating rounded card. Use shared planes, rails and dividers for operational density.

## Signature composition

### Telemetry rail

A thin contextual rail can show Profile, target window and system/content state using compact labels. This creates recognizable precision without fake instrumentation.

### Status lane

Operational pages use a consistent left-edge/status-marker system for Ready, Warning, Publishing, Published and Reconciliation states.

### Split review cockpit

Review uses a deliberate asymmetric composition: content preview dominates, decision controls stay narrow and stable.

### Signal action

The primary action uses `--pa-signal` with dark text. Limit signal-colored primary buttons to one dominant action in a local section.

## Components

Required primitives:

- `AppRail`
- `ProfileSwitcher`
- `PageHeader`
- `SignalButton`
- `SecondaryButton`
- `StatusBadge`
- `TelemetryLabel`
- `MetricTile`
- `TimelineItem`
- `BatchCard`
- `ContentPreview`
- `ReviewDecisionBar`
- `ProgressRail`
- `WarningCallout`
- `EvidenceDrawer`
- `ScheduleDialog`
- `EmptyState`
- `Skeleton`

Feature components must compose these primitives rather than invent local status semantics.

## Interaction states

Every interactive component defines:

```text
default
hover
focus-visible
pressed/active
disabled
loading
error when applicable
```

Focus must remain clearly visible against dark surfaces.

## Motion

Durations:

```text
micro: 120ms
standard: 180ms
panel: 260ms
```

Preferred easing: standard ease-out for entrances, ease-in-out for state relocation.

Use motion for:

- progress transitions;
- drawers/panels;
- content state changes;
- subtle optimistic confirmation.

Do not animate continuous decorative telemetry. Respect `prefers-reduced-motion` and reduce nonessential motion to instant transitions.

## Responsive

Reference widths, not hard device categories:

- wide: >= 1440px;
- desktop: 1024–1439px;
- compact/tablet: 768–1023px;
- mobile: < 768px.

Rules:

- Review preview remains primary; side panel moves below at compact widths.
- App rail collapses before content becomes cramped.
- Tables become cards/list rows where column meaning would be lost.
- Sticky approval/schedule actions must not obscure content or safe areas.

## Accessibility

Baseline target: WCAG 2.2 AA for product UI.

Requirements:

- keyboard complete;
- visible focus;
- semantic headings/landmarks;
- form labels and error association;
- status not color-only;
- reduced-motion support;
- sufficient contrast;
- accessible dialog focus management;
- meaningful alt text for authored visuals and useful generated alt text drafts;
- content previews do not replace actual accessible text.

## Loading model

Prefer progressive semantic state over generic spinners:

```text
Reviewing recent content
Finding fresh angles
Writing
Creating visuals
Checking quality
```

Long operations remain cancelable where cancellation is semantically safe.

## Error language

User-facing errors state outcome and safe next action.

Good:

> “LinkedIn did not confirm publication. This item needs reconciliation and will not be retried automatically.”

Bad:

> “worker-03 Redis stream ack timeout: pending=1”

The latter belongs in diagnostics.

## Visual regression requirement

Every signature component and each primary screen must have desktop + mobile visual snapshots before its slice can be certified. `DESIGN.md` is not considered implemented merely because token constants exist.
