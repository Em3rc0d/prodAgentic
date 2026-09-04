# MK1 Delivery Plan

Planning turns frozen design/architecture into dependency-ordered, certifiable work.

Canonical files:

- `DESIGN_GRAPH.md` — every build-critical design node and closure state.
- `DELIVERY_PLAN.md` — execution phases and sequencing.
- `VERTICAL_SLICES.md` — end-to-end slices with exit criteria.
- `RISK_REGISTER.md` — risks, mitigations and triggers.
- `BUILD_ENTRY_CRITERIA.md` — exact gate for “Take the hummer”.

Rule: implementation may discover new facts, but it may not silently reopen an architectural decision. A material discovery creates an ADR revisit or quarry, updates the graph, and blocks only the dependent slice when necessary.
