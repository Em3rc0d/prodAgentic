# MK1 Control Center (Home)

Status: **FROZEN**

## Job

Home answers four questions in order:

1. What needs my attention?
2. What is ready?
3. What is scheduled/going out?
4. Is the system healthy enough for me to trust that state?

## Desktop composition

### A — Context strip

- greeting/time context;
- active Profile or “All Profiles” switcher;
- compact date/window context.

### B — Operational summary

Four compact metrics:

- Ready for review
- Scheduled
- Published today
- Needs attention

Counts are clickable filters, not vanity cards.

### C — Priority action lane

One dominant card for the highest-value next action, e.g.:

> 4 pieces ready for tomorrow — Review batch

or:

> No content prepared for tomorrow — Generate next batch

### D — Timeline

Unified content timeline across Profiles:

```text
09:00  Tech            Published
13:00  Logan           Scheduled
17:00  Content Seller  Ready
21:00  Tech            Review
```

### E — System trust strip

Default:

> All systems operational

Only degraded user-relevant capabilities expand:

> LinkedIn publishing degraded · manual export remains available

Do not expose worker hostnames, Redis PEL counts, model timeouts, or trace IDs here.

## Empty/first-run mode

If no Profile exists, Home becomes a focused onboarding invitation rather than an empty dashboard.

## Multi-Profile behavior

“All Profiles” is ideal for operations. Selecting one Profile scopes metrics, timeline and quick actions without losing global navigation.

## Mobile

Priority action and needs-attention come first. Metrics become horizontally compact; timeline becomes chronological cards. System status remains a small footer/strip unless degraded.
