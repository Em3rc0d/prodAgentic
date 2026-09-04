# MK1 Code Rules

These rules turn architecture into reviewable implementation constraints.

1. No new MK1 business document without `tenant_id`.
2. No route handler directly publishes externally.
3. No agent writes authoritative domain state directly.
4. No publisher reads mutable revision/draft fields instead of Approval.
5. No Redis-only durable business state.
6. No generic retry from `PUBLISHING` uncertainty.
7. No raw remote asset URL becomes approval authority.
8. No agent stage boundary returns an unversioned opaque blob when a registered contract exists.
9. No critical visual copy is authored only by an image model.
10. No Profile secret/connection token inside snapshots/prompts.
11. No new required Profile form field without design justification.
12. No regeneration overwrites old run/revision provenance.
13. No unsupported metric becomes zero by default.
14. No feature considered done without error path, audit/metrics and tests.
15. No architecture-changing implementation merged without doc/ADR update.
