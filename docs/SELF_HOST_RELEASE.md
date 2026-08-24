# prodAgentic — Self-host release handoff

This document starts at the hosting boundary. The repository is expected to be fully certified before any command here is used. Repository certification **does not deploy prodAgentic**; the operator chooses and controls the hosting service.

## 1. First-release topology

```text
Browser
  -> HTTPS frontend (Next.js)
      -> HTTPS backend (FastAPI)
          -> MongoDB
          -> durable visual asset volume
          -> Gemini/provider APIs
          -> LinkedIn OAuth / publishing APIs
```

The hosting provider is intentionally not prescribed. The same contract can be implemented with separate frontend/backend services or behind an HTTPS reverse proxy, provided the public frontend and backend origins match the configured environment values.

For v1, run **exactly one backend application replica** while the in-process scheduler is enabled. The scheduler performs atomic publication claims, but a single application authority is still the supported first-release topology while visual bytes live on one durable filesystem volume.

## 2. Immutable release inputs

Deploy one exact `main` commit. Do not combine uncommitted files, a different frontend commit, or locally regenerated dependency locks.

Frontend dependency installation must use the committed npm lock. The release gate audits the complete frontend/toolchain graph because browser-test and build tooling also executes code during certification:

```bash
cd frontend
npm ci
npm audit --audit-level=high
npm run build
```

The frontend production build requires an explicit HTTPS backend origin:

```text
NEXT_PUBLIC_API_URL=https://<backend-origin>
```

The backend Docker image installs `backend/requirements.lock` with pip hash checking. `requirements.txt` is dependency intent; `requirements.lock` is the certified Python 3.11 production resolution. Do not replace the lock with a fresh unconstrained install during deployment.

Equivalent non-Docker validation of the locked backend dependency set is:

```bash
cd backend
python -m pip install --require-hashes -r requirements.lock
```

Backend configuration starts from `backend/.env.production.example`. Set secrets in the hosting service; do not commit them.

## 3. Backend production invariants

Set:

```text
PRODAGENTIC_ENV=production
PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_COOKIE_SECURE=true
PRODAGENTIC_COOKIE_SAMESITE=none
CORS_ALLOWED_ORIGINS=https://<frontend-origin>
FRONTEND_URL=https://<frontend-origin>
LINKEDIN_STATIC_FALLBACK_ENABLED=false
```

`FRONTEND_URL` and every CORS origin must be canonical HTTPS origins. Wildcards, HTTP production origins, localhost, trailing slashes, paths, query strings, and fragments are not part of the production contract.

`PRODAGENTIC_ASSET_ROOT` must be an absolute path backed by durable storage. Mount the hosting service's persistent volume at or above that path. A container filesystem that disappears on replacement is not sufficient.

MongoDB is durable authority for ContentRuns, profiles, approvals, schedules, OAuth connection state, and publication evidence. `/health/ready` must not be considered ready when MongoDB is unavailable.

## 4. LinkedIn OAuth contract

Configure the LinkedIn application with the exact backend callback:

```text
https://<backend-origin>/api/integrations/linkedin/callback
```

Backend-only values:

```text
LINKEDIN_CLIENT_ID
LINKEDIN_CLIENT_SECRET
PRODAGENTIC_LINKEDIN_TOKEN_KEY
LINKEDIN_API_VERSION
```

The normal production path is persisted OAuth. Do not enable static token fallback for normal production.

## 5. Health and browser boundary

After starting the backend, require:

```text
GET /health/live  -> 200
GET /health/ready -> 200 READY / READY_WITH_STALE_CACHE
                     or an explicitly accepted DEGRADED readiness state
```

Then verify from the real frontend origin:

1. CORS preflight succeeds only for the configured origin.
2. An unauthenticated protected API request remains `401`.
3. Login creates the HttpOnly Secure session cookie.
4. A mutating request fails without the bound CSRF token and succeeds with it.
5. Logout invalidates the browser session and the next protected request returns `401`.

## 6. Product journey receipt before public release

Without publishing externally yet:

1. Sign in.
2. Create/select a Content Profile.
3. Generate a ContentRun.
4. Render a visual.
5. Reopen the run from Library.
6. Apply a human text edit.
7. Approve the exact text + visual bundle.
8. Record approval ID, bundle SHA-256, asset URL, and visual SHA-256.
9. Schedule the approved run for a future instant.
10. Cancel it.
11. Reopen it and confirm the approval/provenance is unchanged.
12. Restart/recreate the backend **without replacing MongoDB or the asset volume**.
13. Fetch the same visual again and confirm the visual SHA-256 is unchanged.
14. Confirm the same run and approval ID still reopen correctly.

## 7. Separate external LinkedIn proof

Real publication is a separate, explicit external gate. After the production runtime is otherwise certified:

1. Connect the intended LinkedIn member through OAuth.
2. Confirm the app shows the persisted connected identity.
3. Choose one controlled approved ContentRun.
4. Explicitly authorize one smoke publication.
5. Confirm LinkedIn accepted it and that the post is actually visible.
6. Record the external post URN and, when visual, external image URN.
7. Confirm publication evidence references the exact approved bundle digest.
8. Repeating the action for the already-published bundle must not create a duplicate.

## 8. Framework security gate

The repository is moving to the supported Next.js 16.3 line. Next.js announced a scheduled critical security release for **August 26, 2026** affecting the supported 16.3/15.5 lines.

Therefore, before a public deployment made on or after that security release:

1. update Next.js / `eslint-config-next` to the released patched 16.3 version,
2. regenerate `package-lock.json` with npm,
3. run `npm audit --audit-level=high`,
4. run the complete repository CI,
5. require the desktop/mobile Chromium certification to remain green.

Do not bypass this step by pinning an older unsupported line.

## Release definition

The repository is **deploy-ready** when CI is green at the exact release-candidate commit. The hosted runtime is **production-certified** only after the host-specific receipts above. Real LinkedIn publication is certified only after the separately authorized external smoke post.
