# DOCKER-COMPOSE-LOCAL — Build Record

State: **IMPLEMENTATION CANDIDATE PASSED — CERTIFICATION RECEIPT HEAD CI REQUIRED**

Branch: `ops/docker-compose-local-stack`

Base authority: `main@e1a75a0628dc7ee3977ef24004fb867c9d6ced20`, preserving the certified MK1 S0/S1/S2 product-code boundary.

## Objective

Provide one reproducible local command that starts the complete currently-authorized MK1 S0→S2 product surface:

```bash
docker compose up --build
```

The result exposes only loopback host bindings:

```text
127.0.0.1:3000  frontend
127.0.0.1:8000  backend
127.0.0.1:27017 mongo
```

## Scope implemented

- root `docker-compose.yml`;
- production-style `frontend/Dockerfile`;
- frontend Docker build-context exclusions;
- optional `.env.docker.example` overrides;
- persistent Mongo and asset volumes;
- Mongo/backend/frontend healthchecks;
- health-gated startup dependencies;
- dedicated `DOCKER-COMPOSE-LOCAL smoke` GitHub Actions gate;
- Docker-specific operator documentation;
- Docker certification receipt.

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

## Exact implementation candidate

```text
66555f71733308dd25a2274b005cfc1fad647252
```

### Canonical CI

```text
CI #713
run:                34075776900
frontend-test:       101601449819  PASS
backend-test:        101601449951  PASS
UI-01-CERT browser:  101601787273  PASS
```

Browser artifact:

```text
id:      10002045099
name:    ui-01-cert-evidence
sha256:  cdfdf9fdc0b4f5b755b47b6ac4aa7f2f5fd7f8ce50b650f022d432bfe1dde490
```

### Docker Compose Local

```text
Docker Compose Local #5
run:  34075776893
job:  101601495233
PASS
```

Dedicated Compose gates passed:

```text
compose model validation              PASS
backend + frontend image build        PASS
health-gated full-stack startup       PASS
Mongo ping                            PASS
backend /health/live                  PASS
frontend HTTP                         PASS
local auth login + CSRF               PASS
log evidence upload                   PASS
CI teardown                           PASS
```

Compose artifact:

```text
id:      10001997661
name:    docker-compose-local-evidence
sha256:  30377ca75a8ae2c88a9e6fe87bb592fedae85f84963388f436f75d8c3871bce5
```

## Candidate decision

The exact implementation candidate satisfies the frozen operational contract and both required test families.

No unresolved implementation contradiction was found after the final hardening that changed LinkedIn from placeholder configuration to **truly unconfigured by default**.

The authoritative certification details are recorded in:

```text
mk1/test/evidence/DOCKER_COMPOSE_LOCAL/CERTIFICATION.md
```

## Receipt-head rule

This build record and the certification receipt bind the successful candidate evidence into the repository. Their commit is therefore a new documentation receipt head.

The exact receipt head must itself pass unchanged:

```text
canonical CI
  backend-test
  frontend-test
  UI-01-CERT browser

Docker Compose Local
  DOCKER-COMPOSE-LOCAL smoke
```

Only after both are fully green is PR #39 merge-approved.

Any code or documentation mutation after that green receipt invalidates merge approval until the new exact head passes both workflow families again.

## Post-merge rule

After merge, the exact `main` SHA must pass both workflow families before operator use is promoted.

Once that post-merge gate closes, the operator command is:

```bash
git pull
docker compose up --build
```

and product-facing acceptance continues with `mk1/test/LOCAL_ACCEPTANCE.md`.
