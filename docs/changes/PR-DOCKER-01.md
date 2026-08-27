# PR-DOCKER-01 — One-command prodAgentic Docker Stack

Status: IMPLEMENTED / CI GREEN
Branch: `feat/docker-one-command-stack`
Base: `feat/content-intelligence-foundation`

## Intent

Provide one reproducible command that starts the complete current prodAgentic runtime on a single Docker host:

```bash
docker compose up --build -d
```

Public entrypoint:

```text
http://localhost:8080
```

## Implemented topology

```text
browser
  |
  v
nginx gateway :8080
  |-- /                  -> Next.js :3000
  |-- /api/*             -> FastAPI :8000
  |-- /assets/*          -> FastAPI :8000
  `-- /health/*          -> FastAPI :8000

FastAPI -> MongoDB :27017
```

Services:
- nginx gateway,
- Next.js frontend,
- FastAPI backend + scheduler,
- MongoDB 7.

Persistence:
- `mongo_data` named volume,
- `render_assets` named volume.

## Security boundary

Observed configuration:
- only nginx publishes a host port,
- MongoDB is not host-exposed,
- FastAPI is not host-exposed,
- Next.js is not host-exposed,
- backend secrets come from `backend/.env`,
- `backend/.env` is excluded from Docker build context,
- `/docs` and `/openapi.json` are blocked at the public gateway,
- application APIs retain prodAgentic signed HttpOnly-session + CSRF protection,
- frontend uses same-origin `/api` through the gateway.

## CI evidence

Implementation head before this receipt:

`6e0a778d1495e1788541140b9a54ac404c1ca497`

GitHub Actions run:

`33096853996`

Observed:
- Compose contract validation: PASS.
- Backend image build: PASS.
- Frontend standalone image build: PASS.
- Mongo container startup/health: PASS.
- FastAPI container startup/health: PASS.
- Next.js container startup/health: PASS.
- nginx gateway startup: PASS.
- `GET /health/live` through public gateway: PASS.
- frontend `/` through public gateway: PASS.
- `/openapi.json` public exposure test: BLOCKED as required.
- full stack teardown: PASS.
- backend smoke import: PASS.
- backend compile: PASS.
- backend pytest: **118 passed, 1 warning in 38.00s**.
- frontend lint: PASS.
- frontend tests: PASS.
- frontend production build: PASS.

## Operational contract

Required local secret file when authentication is enabled:

```env
GEMINI_API_KEY=<secret>
PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=<12+ chars>
PRODAGENTIC_SESSION_SECRET=<32+ random chars>
```

The compose runtime overrides `MONGO_URI` to `mongodb://mongo:27017` so users do not need to provision Mongo separately for this topology.

For plain local HTTP, `PRODAGENTIC_COOKIE_SECURE=false` is the default compose override. When deployed behind HTTPS, it must be set to `true`.

## Non-goals / truth boundary

This certification proves a **single-host Docker topology**. It does not claim:
- managed TLS,
- multi-host failover,
- MongoDB authentication between untrusted networks,
- managed backups,
- horizontal scheduler coordination,
- multi-replica publication coordination.

## Verdict

`PR-DOCKER-01`: PASS.

The current prodAgentic application can be built and started as a complete isolated stack with one Docker Compose command.