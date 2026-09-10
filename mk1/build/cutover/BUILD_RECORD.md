# PHASE H BUILD RECORD — Production Cutover

Status: **IMPLEMENTATION COMPLETE / CERTIFICATION PENDING**

Base authority: `main@f71c44eda4cf9769c9eb216469fbcd741e789220`
Formalization authority: `85d27541e566d8f8124799ca61e0e52016f4983a`

## Implemented scope

```text
backend/core/feature_flags.py
backend/core/cutover.py
backend/main.py
backend/.env.example
backend/tests/test_phase_h_cutover.py
frontend/Dockerfile
frontend/.env.production.example
docker-compose.s10.yml
docker-compose.s11.yml
docker-compose.cutover.yml
.github/workflows/phase-h-cutover-cert.yml
mk1/build/cutover/{FORMALIZATION.md,RUNBOOK.md,BUILD_RECORD.md,CANDIDATE.md}
```

## Authority transfer

`MK1_PRODUCTION_CUTOVER=true` is a fail-closed authority claim. It requires every certified MK1 V1 feature flag to be enabled.

When active:

- MK0 scheduler is disabled by the already-certified S10 publication cutover rule;
- side-effectful MK0 HTTP generation/mutation/publication paths return `410 MK0_WRITE_AUTHORITY_RETIRED`;
- historical MK0 GET reads remain available;
- MK1 Profile/Batch/production/review/export/publish/analytics/learning paths remain mounted;
- no MK0 data is deleted or rewritten.

## Production readiness evidence

`GET /health/cutover` reports a safe, public readiness snapshot containing only booleans/states required by release monitoring. It requires:

- cutover flag active;
- Mongo ready;
- MK0 scheduler absent;
- S10 publish worker running;
- S11 analytics worker running.

Provider tokens/IDs/user content are excluded.

## Production-mode release overlay

`docker-compose.cutover.yml` overlays the certified local/S9/S10/S11 stack and runs the backend under `PRODAGENTIC_ENV=production` with:

- auth enabled;
- secure cookie / SameSite=None;
- canonical HTTPS public origins;
- all MK1 flags enabled;
- cutover enabled;
- Redis/Mongo/assets durable;
- LinkedIn static fallback disabled.

The frontend image now freezes `NEXT_PUBLIC_MK1_PUBLISHING` and `NEXT_PUBLIC_MK1_ANALYTICS` at build time. S10/S11 Compose overlays pass those flags as Docker build args as well as runtime metadata, so local/cert/cutover artifacts share one feature-flag meaning.

## Rollback

Rollback is configuration-only and schema-preserving:

1. pause mutations;
2. set `MK1_PRODUCTION_CUTOVER=false`;
3. disable `MK1_PUBLISH_WORKER` before restoring MK0 scheduler authority;
4. disable additional MK1 flags if required;
5. restart;
6. reconcile in-flight Publication states before retrying through another authority.

No MK1 collection deletion is required.

## Provider gate

Phase H does not authorize a public LinkedIn post. Certification records:

```text
live_linkedin_publish = NOT_EXERCISED_OPERATOR_AUTH_REQUIRED
live_linkedin_analytics_read = NOT_EXERCISED_CAPABILITY_DEPENDENT
```

S8 ManualExport remains the provider-independent certified distribution path.

## Certification

Candidate must pass **13/13** workflows pre-merge and post-merge:

CI, Docker Compose Local, S3–S12, and `PHASE-H Production Cutover Cert`.

Phase H workflow has two jobs:

1. authority/rollback/contracts on real Mongo+Redis plus S0/S1/S2/S11/S12/restart regressions;
2. fresh disposable production-mode Docker stack including startup, auth, legacy retirement, historical read, frontend, Mongo/Redis restart durability and cutover readiness after restart.

No tracked file is modified after exact candidate freeze.
