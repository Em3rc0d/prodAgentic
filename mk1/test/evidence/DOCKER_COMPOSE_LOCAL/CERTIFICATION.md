# DOCKER-COMPOSE-LOCAL Certification

Certification state: **CERTIFICATION RECEIPT — MERGE APPROVED ONLY AFTER THIS RECEIPT HEAD PASSES BOTH WORKFLOWS UNCHANGED**

Operational slice: `DOCKER-COMPOSE-LOCAL`

Branch: `ops/docker-compose-local-stack`

Base: `main@e1a75a0628dc7ee3977ef24004fb867c9d6ced20`

## Objective

Certify the one-command local MK1 S0→S2 stack:

```bash
docker compose up --build
```

The stack must start MongoDB 7, the FastAPI backend and the production-style Next.js frontend with health-gated ordering, persistent local volumes, loopback-only host bindings, local auth enabled and no implicit external publishing authority.

## Exact implementation candidate

```text
66555f71733308dd25a2274b005cfc1fad647252
```

No earlier Docker candidate or workflow run is certification authority for this receipt.

## Canonical CI evidence

Workflow:

```text
CI #713
run: 34075776900
head: 66555f71733308dd25a2274b005cfc1fad647252
result: SUCCESS
```

Jobs:

```text
frontend-test       101601449819  PASS
backend-test        101601449951  PASS
UI-01-CERT browser  101601787273  PASS
```

The browser evidence artifact is:

```text
id:      10002045099
name:    ui-01-cert-evidence
sha256:  cdfdf9fdc0b4f5b755b47b6ac4aa7f2f5fd7f8ce50b650f022d432bfe1dde490
```

Canonical CI therefore proves the Docker operational additions did not regress the accepted backend, frontend or desktop/mobile browser product gates.

## Dedicated Docker Compose evidence

Workflow:

```text
Docker Compose Local #5
run: 34075776893
head: 66555f71733308dd25a2274b005cfc1fad647252
job: 101601495233
result: SUCCESS
```

The exact candidate passed every dedicated Compose step:

```text
Docker/Compose available              PASS
Compose model validation              PASS
backend + frontend image build        PASS
health-gated full-stack startup       PASS
Mongo ping                            PASS
backend /health/live                  PASS
frontend HTTP                         PASS
default local auth login + CSRF       PASS
Compose log evidence capture          PASS
CI stack teardown with volumes        PASS
```

Compose evidence artifact:

```text
id:      10001997661
name:    docker-compose-local-evidence
sha256:  30377ca75a8ae2c88a9e6fe87bb592fedae85f84963388f436f75d8c3871bce5
```

## Certified implementation properties

The reviewed candidate implements these local operational properties:

- one-command startup through `docker compose up --build`;
- MongoDB 7 service with persistent named volume;
- existing hash-locked backend image reused unchanged;
- production-style Node 24 / Next.js frontend image;
- browser-visible API origin frozen to `http://127.0.0.1:8000` at frontend build time;
- internal backend→Mongo routing through Docker service DNS;
- host ports bound to `127.0.0.1` only;
- health-gated Mongo → backend → frontend startup;
- persistent asset volume;
- MK1 S0/S1/S2 gates enabled explicitly;
- image rendering and scheduler disabled for the bounded S0→S2 acceptance stack;
- LinkedIn static fallback disabled;
- LinkedIn OAuth credentials empty by default, so integration authority is absent until deliberately configured;
- optional Gemini/provider credentials remain outside the checked-in stack;
- `.env.docker` ignored and `.env.docker.example` contains only local override guidance.

## Security / side-effect boundary

This certification is **local development/acceptance only**. It does not certify production deployment.

The default Compose contract intentionally does not authorize:

- S3 Research/Writer/Editor/Visual execution;
- LinkedIn OAuth connection;
- LinkedIn static-token fallback;
- automatic/scheduled publication;
- image generation/rendering;
- production network exposure;
- production credentials or TLS policy.

A local operator may later provide optional credentials deliberately, but such a configuration is outside this receipt unless separately tested.

## Persistence / recovery boundary

Named volumes:

```text
prodagentic_mongo_data
prodagentic_assets
```

Normal:

```bash
docker compose down
```

preserves evidence and assets.

Destructive local reset:

```bash
docker compose down -v
```

is intentionally explicit.

## Receipt-head rule

The implementation candidate `66555f71733308dd25a2274b005cfc1fad647252` passed both required workflow families unchanged and has been manually reviewed.

This certification document and the matching build record now bind that evidence into the repository. The commit created by those documentation mutations is a **new receipt head** and is not merge-approved merely because this file exists.

The exact receipt head must itself pass unchanged:

```text
CI
  backend-test
  frontend-test
  UI-01-CERT browser

Docker Compose Local
  DOCKER-COMPOSE-LOCAL smoke
```

If both workflows are fully green on the exact receipt head, this receipt becomes effective and the Docker local stack is **CERTIFIED — MERGE APPROVED** without further mutation.

If either workflow fails, the receipt remains blocked and the failure must be repaired on a new candidate.

## Post-merge rule

After merge, the exact `main` merge SHA must again pass both workflow families before the operator is told to rely on the one-command stack from `main`.

Operator acceptance then continues with:

```text
mk1/test/LOCAL_ACCEPTANCE.md
```

Docker certification proves the startup topology. It does not substitute for the product-facing S0→S2 local acceptance receipt.
