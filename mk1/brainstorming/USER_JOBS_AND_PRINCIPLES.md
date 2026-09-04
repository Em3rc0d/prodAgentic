# User Jobs and Product Principles

Status: **PROMOTED**

## Primary user model

MK1 is designed first for an operator managing one or more editorial identities. The operator may be a creator, founder, engineer, marketer, small team, or business owner. The system must not require them to think like an AI engineer or workflow operator.

## Core jobs

### J1 — Establish an identity

> Teach prodAgentic who this Profile is, what it wants, who it speaks to, and what good examples look like.

The default interaction is short. Deep policy is inferred or progressively disclosed.

### J2 — Prepare the next publishing window

> Give me a useful batch for tomorrow/this week without repeating what I already said.

The system chooses candidate breadth, role balance and novelty checks internally.

### J3 — Review decisions, not machinery

> Show me the content, important warnings and why something needs attention.

Low-level model/provider/queue telemetry is hidden unless the user asks for diagnostics.

### J4 — Control the irreversible boundary

> Let me approve exactly what is allowed to leave the system.

Approval is an explicit human action in V1.

### J5 — Trust execution

> If I schedule/publish something, show whether it is pending, succeeded, failed safely, or needs reconciliation.

No silent duplicates. No false success.

### J6 — Improve over time

> Learn what works without turning my account into the same post repeated forever.

Performance is subordinate to brand, safety, novelty and diversity.

## Principles

### P1 — Zero-friction first

Happy-path screens should ask only for decisions the system cannot responsibly infer.

### P2 — Progressive disclosure

Expose three conceptual levels:

- Simple — user task and result.
- Guided — reasons, warnings and overrides.
- Advanced — contracts, agents and diagnostics.

### P3 — Opinionated defaults

Batch size, cooldown, roles, format mix, CTA policy and scheduling recommendations should have Profile-aware defaults.

### P4 — Explain without leaking machinery

Prefer “Too similar to a post from 3 days ago” over embedding thresholds or vector-distance jargon.

### P5 — Safe autonomy

Automate reversible work aggressively; keep irreversible or uncertain actions behind explicit policy/authority boundaries.

### P6 — Evidence over assumption

Important state transitions must be reconstructable from snapshots, digests, receipts, audit events and correlation IDs.

### P7 — Memory before generation

No batch should act as if the Profile started today.

### P8 — Determinism where possible

Do not spend LLM judgment on checks that normal software can prove.

### P9 — Graceful degradation

A failed visual must not destroy valid copy. A missing platform integration must not destroy an approved asset. A Redis outage must not erase schedule authority.

### P10 — User language, system depth

The user sees “Ready”, “Needs review”, “Scheduled”, “Published”; operations may see traces, attempts, hashes and queue IDs for the same reality.
