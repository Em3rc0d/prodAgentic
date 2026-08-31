# PR-DEPLOY-01 — First-release production deployment contract

## Purpose

Turn the certified prodAgentic application into one reproducible first-release production topology without weakening persistence, approval authority, scheduling, or visual-byte integrity.

## First-release topology

```text
Browser
  |
  v
Vercel — Next.js frontend
  |
  | credentialed HTTPS API/SSE
  v
Railway — FastAPI backend (EXACTLY ONE application replica)
  |             |                |
  |             |                +--> LinkedIn REST API
  |             +-------------------> Gemini / provider APIs
  |
  +--> durable MongoDB
  |
  +--> Railway persistent volume
       /data/prodagentic
         └── assets/renders/*
```

### Why exactly one backend replica for v1

The scheduler is multi-instance safe for lifecycle claiming through Mongo, but the approved visual bytes are intentionally stored on the backend service's mounted filesystem volume. A service-local volume is not a shared object store. Running multiple application replicas could allow one replica to claim a scheduled run whose approved bytes exist only on another replica.

The v1 production contract is therefore one backend replica with one persistent volume. Horizontal backend scaling is a later architecture change and requires shared durable asset storage.

## Railway backend

Connect the GitHub repository and deploy `main` with:

- Root Directory: `/backend`
- Config file path: `/backend/railway.toml`
- Dockerfile: auto-detected from `/backend/Dockerfile`
- Replicas: `1`
- Public HTTPS domain: generated or custom
- Persistent volume mount: `/data/prodagentic`
- `PRODAGENTIC_ASSET_ROOT=/data/prodagentic/assets`
- Production variables: use `backend/.env.production.example` as the contract; store secrets only in the provider secret store

The Railway activation healthcheck is `/health/ready`, not `/health/live`. Production must not receive traffic unless provider configuration and Mongo persistence are ready.

## Vercel frontend

Create a Vercel project from the same GitHub repository with:

- Root Directory: `frontend`
- Production branch: `main`
- `NEXT_PUBLIC_API_URL=https://<railway-backend-domain>`

After the first frontend deployment establishes its production domain, set the backend variable:

```text
CORS_ALLOWED_ORIGINS=https://<production-frontend-domain>
```

Then redeploy/restart the backend so CORS uses the exact production origin.

Because the first-release frontend and backend use separate HTTPS origins, keep:

```text
PRODAGENTIC_COOKIE_SECURE=true
PRODAGENTIC_COOKIE_SAMESITE=none
```

## Provider/version boundary

At release preparation on 2026-08-31, LinkedIn's latest documented Marketing API version is `202608`. Set:

```text
LINKEDIN_API_VERSION=202608
```

Re-check LinkedIn's supported version immediately before any later release if significant time has passed.

## Production certification sequence

Do not collapse these checks into a generic "site works" claim.

### DEPLOY-01A — immutable source receipt

Record the exact `main` commit SHA deployed to both services.

### DEPLOY-01B — readiness

Prove:

- backend `/health/live` returns HTTP 200
- backend `/health/ready` returns HTTP 200 with a ready/degraded-ready application status
- frontend production route loads
- browser CORS preflight succeeds from the exact frontend origin
- unauthenticated protected API calls remain HTTP 401

### DEPLOY-01C — authenticated browser boundary

From the deployed frontend:

1. sign in through the admin boundary
2. verify the HttpOnly secure session works cross-origin
3. verify CSRF-protected mutation succeeds only with the bound token
4. sign out and verify protected access returns to 401

### DEPLOY-01D — durable product journey without external publication

1. sign in
2. create/select a Content Profile
3. generate a ContentRun
4. render a visual
5. reopen the run from the Content Library
6. human-edit final copy
7. approve text + visual
8. record approval ID, bundle SHA-256, visual asset URL and visual SHA-256
9. schedule for a sufficiently distant future time
10. cancel the schedule before it becomes due
11. reopen and verify immutable approval/provenance remain intact

This proves production application boundaries without creating a public LinkedIn post.

### DEPLOY-01E — persistent-volume restart proof

Using an approved visual from DEPLOY-01D:

1. fetch the approved visual bytes and record SHA-256
2. restart/redeploy the Railway backend WITHOUT deleting/replacing the volume
3. wait for `/health/ready` to return HTTP 200
4. fetch the same approved visual asset again
5. recompute SHA-256 and prove it matches the approval snapshot
6. reopen the same ContentRun and prove approval ID + bundle digest are unchanged

Only then may the production persistence gate be marked certified.

### DEPLOY-01F — real LinkedIn smoke (separate explicit authorization)

The automated release suite already proves the publication state machine with an injected provider. The final external gate must use a real LinkedIn account/token and must not be triggered implicitly by deployment work.

Before this step, obtain explicit approval for the exact post/account to be used.

Then perform one controlled publication and prove:

- LinkedIn accepted the request
- the post is actually visible on LinkedIn
- prodAgentic stores the real external post URN
- if visual, prodAgentic stores the external image URN
- persisted publication evidence carries the exact approved bundle digest
- a repeated product action does not duplicate the post

## Release definition

`PRODUCTION DEPLOYMENT = CERTIFIED` only after DEPLOY-01A through DEPLOY-01E have receipts.

`REAL LINKEDIN PROOF = CERTIFIED` only after DEPLOY-01F.

Only after both gates close should the first production release be tagged.
