# MK1 Architecture Authority

Status: **DESIGN FREEZE**

Architecture translates the product contract into stable boundaries, invariants and replaceable adapters.

## Canonical documents

- `SYSTEM_ARCHITECTURE.md`
- `DOMAIN_MODEL.md`
- `STATE_MACHINES.md`
- `INVARIANTS.md`
- `EDITORIAL_ENGINE.md`
- `AGENT_ARCHITECTURE.md`
- `CONTRACTS.md`
- `VISUAL_SYSTEM.md`
- `GOVERNANCE_QA.md`
- `DATA_ARCHITECTURE.md`
- `EXECUTION_ARCHITECTURE.md`
- `PUBLISHING.md`
- `ANALYTICS_LEARNING.md`
- `SECURITY_OBSERVABILITY.md`
- `INVALIDATION_RULES.md`
- `adr/`

## Architecture rule

MK1 is a **modular monolith with separately runnable workers**, not a collection of microservices. Boundaries are code/domain boundaries first. Deployment decomposition is allowed later only when measured operational evidence justifies it.

## Dependency direction

```text
UI/API
  -> application services
      -> domain contracts
          <- infrastructure adapters
```

Agents and provider adapters do not own domain state. Application services coordinate them and persist authoritative transitions through repositories.
