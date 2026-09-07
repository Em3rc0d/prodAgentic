# DOCKER-COMPOSE-LOCAL — Build Record

State: **IMPLEMENTED CANDIDATE — EXACT-HEAD CERTIFICATION REQUIRED**

Branch: `ops/docker-compose-local-stack`

Base authority: MK1 S0/S1/S2 certified product line plus the reconciled local-acceptance documentation on `main`.

## Objective

Provide one reproducible local command that starts the complete currently-authorized MK1 S0→S2 product surface:

```bash
docker compose up --build
```

The result must expose only loopback host bindings:

```text
127.0.0.1:3000  frontend
127.0.0.1:8000  backend
127.0.0.1:27017 mongo
```

## Scope

This operational slice adds:

- root `docker-compose.yml`;
- production-style `frontend/Dockerfile`;
- frontend Docker build-context exclusions;
- optional `.env.docker.example` overrides;
- persistent Mongo and asset volumes;
- Mongo/backend/frontend healthchecks;
- health-gated startup dependencies;
- a dedicated `DOCKER-COMPOSE-LOCAL smoke` GitHub Actions gate;
- Docker-specific operator documentation.

The existing backend Dockerfile remains authoritative and is reused unchanged.

## Frozen local boundaries

- Compose is **development/local only**, never a production deployment receipt.
- Host ports bind to `127.0.0.1`, not all interfaces.
- Mongo service discovery uses the internal hostname `mongo`.
- The browser-visible API origin remains `http://127.0.0.1:8000` because Docker-internal hostname `backend` is not resolvable from the host browser.
- MK1 S0/S1/S2 flags are enabled.
- S3 is not authorized by this stack.
- image rendering and scheduler are disabled for the S0→S2 acceptance surface.
- LinkedIn static fallback is disabled.
- LinkedIn OAuth credentials are empty by default, so the integration remains unconfigured until explicitly supplied by the operator.
- no real secret is checked into the repository.
- local default auth credentials are acceptable only because all checked-in host bindings are loopback-only; operators should override them before using non-test local data.

## Persistence

Named volumes:

```text
prodagentic_mongo_data
prodagentic_assets
```

`docker compose down` preserves them.

`docker compose down -v` intentionally destroys them.

## Frontend image contract

The frontend image uses Node 24 and a multi-stage build:

```text
deps -> npm ci
builder -> production Next build -> npm prune --omit=dev
runner -> production deps + .next + public, non-root node user
```

Public MK1/API values are build arguments because Next.js freezes `NEXT_PUBLIC_*` inputs into the client build.

## Health contract

```text
Mongo ping healthy
  -> backend starts
  -> GET /health/live healthy
  -> frontend starts
  -> frontend HTTP healthy
```

Full `/health/ready` is deliberately not the Compose health gate because it includes provider readiness. S0→S2 deterministic planning may be locally accepted without a configured Gemini key.

## Certification requirements

The exact candidate head must pass:

```text
canonical CI
  backend-test
  frontend-test
  UI-01-CERT browser

Docker Compose Local
  compose model validation
  backend image build
  frontend image build
  health-gated full stack start
  Mongo ping
  backend liveness
  frontend HTTP
  default local auth login
  evidence log upload
  clean CI teardown
```

No merge is authorized if either workflow is red or incomplete.

## Operator test after merge

Once exact-head CI and post-merge CI are green, the operator should run:

```bash
git pull
docker compose up --build
```

and continue with `mk1/test/LOCAL_ACCEPTANCE.md`.
