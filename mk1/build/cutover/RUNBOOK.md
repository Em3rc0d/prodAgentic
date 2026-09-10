# PHASE H RUNBOOK — Production Cutover

Status: **RELEASE CONTRACT**

This runbook governs the first MK1 production cutover. It is intentionally reversible and does not remove MK0 historical code/data.

## 1. Preconditions

Required authority before cutover:

```text
S0–S12 = CERTIFIED / CLOSED
main authority = exact Phase H parent
Phase H candidate = immutable exact SHA
pre-merge certification = 13/13 SUCCESS
```

Operational prerequisites:

- production Mongo and Redis are durable/backed up;
- approved asset root is durable and writable;
- frontend/backend public origins are canonical HTTPS origins;
- admin password/session secret are production-grade secrets;
- `PRODAGENTIC_COOKIE_SECURE=true`;
- `PRODAGENTIC_COOKIE_SAMESITE=none`;
- `CORS_ALLOWED_ORIGINS` explicitly contains `FRONTEND_URL` and has no wildcard;
- `LINKEDIN_STATIC_FALLBACK_ENABLED=false`;
- LinkedIn public posting is not performed unless separately authorized.

## 2. Cutover configuration

Enable all certified MK1 authorities together:

```text
MK1_ENABLED=true
MK1_PROFILE_V2=true
MK1_BATCH_PLANNING=true
MK1_STRUCTURED_AGENT_CELL=true
MK1_VISUALSPEC=true
MK1_RENDER_WORKER=true
MK1_REVIEW_APPROVAL=true
MK1_MANUAL_EXPORT=true
MK1_REDIS_TRANSPORT=true
MK1_PUBLISH_WORKER=true
MK1_ANALYTICS_WORKER=true
MK1_PLANNER_LEARNING=true
MK1_PRODUCTION_CUTOVER=true
```

`MK1_PRODUCTION_CUTOVER=true` fails startup if any required child flag is false.

`SCHEDULER_ENABLED` may remain configured, but `MK1_PUBLISH_WORKER=true` owns scheduler/publication authority and suppresses the MK0 scheduler at runtime.

## 3. Deploy order

1. snapshot/backup Mongo state and record backup receipt outside the repo;
2. verify Redis persistence policy and connectivity;
3. deploy backend/renderer with the Phase H certified image/SHA;
4. wait for `/health/live`;
5. require `/health/cutover` = `READY`;
6. deploy frontend built from the same certified tree with all MK1 public flags enabled;
7. verify login/session/CSRF flow;
8. perform authenticated MK1 smoke without public provider side effects;
9. verify legacy writes return `410 MK0_WRITE_AUTHORITY_RETIRED` while historical GETs remain available;
10. verify ManualExport path;
11. only if separately authorized, perform LinkedIn live smoke and capture provider receipt;
12. monitor worker errors/DLQ/queue lag before declaring operational acceptance.

## 4. Required smoke evidence

Capture:

- deployed commit/image identity;
- `/health/live` response;
- `/health/cutover` response;
- feature-flag safe snapshot;
- auth login/session success;
- legacy write 410 result;
- historical legacy GET result;
- MK1 profile + Batch creation result;
- review/approval evidence from certified path or fresh non-provider fixture;
- ManualExport receipt/hash;
- Mongo/asset persistence after restart;
- Redis worker reconnect evidence;
- LinkedIn live status as either:
  - `EXERCISED + receipt`, or
  - `NOT_EXERCISED / OPERATOR_AUTH_REQUIRED`.

Never record OAuth tokens, passwords, session cookies, provider bearer tokens or raw secrets in receipts.

## 5. Rollback

Rollback does not require schema reversal.

### Fast authority rollback

1. stop incoming user mutations during the transition window;
2. set `MK1_PRODUCTION_CUTOVER=false`;
3. disable `MK1_PUBLISH_WORKER` before restoring MK0 scheduling authority;
4. disable other MK1 child flags that must be rolled back;
5. restart backend;
6. verify MK0 scheduler state and legacy write path reachability;
7. keep MK1 collections intact as historical evidence; do not delete them;
8. reconcile any in-flight S10 Publication in `PUBLISHING/NEEDS_RECONCILIATION` before retrying through either authority.

Do **not** enable MK0 scheduler publication while `MK1_PUBLISH_WORKER=true`.

### Roll-forward preference

If the failure is isolated to analytics/learning while publication authority is healthy, prefer disabling the affected MK1 child only after leaving cutover mode first. `MK1_PRODUCTION_CUTOVER` intentionally forbids a partially enabled authority claim.

## 6. Provider boundary

Phase H authorization is authorization to cut software authority, **not** authorization to create a public LinkedIn post.

A live LinkedIn smoke requires an explicit operator decision made with a known approved content bundle and connected account. Without that authorization, the release receipt records the external gate and uses ManualExport + mocked/provider contract evidence already certified by S8/S10/S11.

## 7. Post-cutover observation window

During the rollback window:

- preserve MK0 code and historical collections;
- do not run cleanup migrations;
- monitor publish/analytics worker failures and Redis DLQs;
- compare Schedule/Publication counts for duplicate authority anomalies;
- verify no new MK0 `posts`/`content_runs` authority is created through HTTP paths;
- retain backup and cutover receipts.

MK0 compatibility cleanup is a separate future slice and must not be mixed into Phase H.
