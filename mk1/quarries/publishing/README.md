# Q-PUBLISH-01 — Additional automatic platform adapters

**State:** PARKED (non-blocking)

## Question

Which Instagram/TikTok/other official capabilities can be safely supported for publishing, scheduling and analytics under current APIs and authorization constraints?

## Required evidence before promotion

- official current API documentation/version;
- app/account eligibility;
- auth scopes;
- media/format limits;
- idempotency/reconciliation possibilities;
- analytics metrics/freshness;
- live sandbox/authorized smoke where possible;
- fallback behavior.

## Current architecture answer

LinkedIn is automatic V1. ManualExport covers unsupported channels honestly.

## Promotion

Add a PlatformAdapter only after capability contract tests and release certification. Do not bypass ManualExport based on unofficial automation assumptions.
