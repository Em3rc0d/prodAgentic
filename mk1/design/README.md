# MK1 Design Authority

This directory defines the user-facing product contract for MK1.

Design answers **what the user experiences and what the product promises**. Architecture may choose how to implement those promises but may not silently weaken them.

## Canonical design files

1. `PRODUCT.md` — product surface, scope, autonomy and success metrics.
2. `INFORMATION_ARCHITECTURE.md` — navigation and feature ownership.
3. `USER_JOURNEYS.md` — end-to-end happy/error paths.
4. `PROFILE_SETUP.md` — low-friction editorial identity onboarding.
5. `CREATE_FLOW.md` — batch request and generation progress.
6. `CONTROL_CENTER.md` — Home cockpit.
7. `REVIEW.md` — review, editing, regeneration and approval UX.
8. `CALENDAR_ANALYTICS.md` — scheduling and learning surfaces.
9. `DESIGN.md` — visual system, tokens, components, responsive/accessibility/motion rules.

## Design rule

A backend concept does not automatically deserve a navigation item or form field.

Every visible control must answer:

- Which user job does this serve?
- Can the system infer a safe default instead?
- Is this needed on the happy path or only under progressive disclosure?
- What happens when the action fails?

If a setting cannot answer those questions, it belongs in policy, inference, advanced settings, or operations — not primary UI.
