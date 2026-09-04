# MK1 Risk Register

Scale: probability/impact `L/M/H`.

| ID | Risk | P | I | Mitigation / gate | Trigger |
|---|---|---|---|---|---|
| R01 | Big-bang rewrite breaks proven MK0 safety | M | H | vertical slices, feature flags, compatibility reads, separate cutover | slice changes multiple authorities simultaneously |
| R02 | `ContentRun` semantics leak back into MK1 aggregate design | M | H | ADR-0002, domain contract tests | new code stores approval/schedule directly on GenerationRun |
| R03 | Novelty false positives block useful content | M | M | multi-layer explainability, configurable policy, golden calibration | high human override rate |
| R04 | Novelty false negatives repeat topics/angles | M | H | published/scheduled memory hard inclusion, golden adversarial pairs | repeated real account content |
| R05 | Agent structured output instability | M | M | schema repair budget, provider routing, contract fixtures | repair rate exceeds SLO |
| R06 | Writer/Editor invent unsupported claims | M | H | claim IDs, contract gate, semantic QA | claim without ResearchPack support |
| R07 | Visuals look technically valid but low quality/generic | M | H | signature design system, golden visual snapshots, Profile design policies | human visual rejection remains high |
| R08 | Chromium renderer difficult to operate | M | M | port abstraction, container smoke, resource metrics | crash/memory/latency exceeds budget |
| R09 | Redis duplicate/lost transport causes side-effect errors | M | H | Mongo outbox, at-least-once assumptions, domain atomic claims | discrepancy between outbox/domain/stream |
| R10 | Publication crash creates duplicate public content | L/M | H | no blind replay, reconciliation state, idempotency key | PUBLISHING without receipt |
| R11 | Platform API/version drift | H | M/H | capability snapshots, release-time version quarry/check, adapter tests | provider deprecation/auth error |
| R12 | Cross-tenant data leak after commercial expansion | L | Critical | tenant-scoped repos from S0, negative tests, server-derived context | any query without tenant scope |
| R13 | Migration leaves two competing sources of truth | M | H | authority-by-slice plan, audit/backfill, cutover checklist | same action writable through MK0 and MK1 without explicit projection |
| R14 | Config-heavy UI recreates backend schema as forms | M | H | Profile Setup contract, UI review gate | new required field not justified by user job |
| R15 | Cost/latency explodes from candidate pool + multi-agent calls | M | M | bounded pool/retries, model profiles, cost telemetry | batch p95/cost exceeds budget |
| R16 | Analytics encourages false causal claims/overfitting | M | M | snapshot + confidence summary, performance last priority | UI/Planner says “caused” without experiment |
| R17 | Asset store bytes disappear after approval | L/M | H | durable root, restart test, verify before publish | hash/file missing on reopen |
| R18 | External research prompt injection changes agent behavior | M | H | untrusted-data boundary, tool permissions, adversarial tests | retrieved content alters instruction hierarchy |

## Risk review cadence

- review before each slice starts;
- update after any incident or failed certification;
- a risk becomes a design-graph `REVISIT` only when mitigation requires changing an accepted contract.
