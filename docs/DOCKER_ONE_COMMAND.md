# prodAgentic — One-command Docker stack

Status: implementation branch `feat/docker-one-command-stack`

## Goal

Run the complete current prodAgentic stack with one command after secrets are present:

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:8080
```

Only the gateway is exposed to the host. Frontend, FastAPI and MongoDB remain on an internal Docker network.

## Services

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

The backend scheduler runs in the FastAPI container. Mongo data and generated render bytes use named Docker volumes.

## Required secrets

The compose stack intentionally reuses `backend/.env`. It is excluded from the backend Docker build context and must never be committed.

At minimum, when auth is enabled:

```env
GEMINI_API_KEY=<your key>
PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=<at least 12 characters>
PRODAGENTIC_SESSION_SECRET=<at least 32 random characters>
```

`MONGO_URI` from `backend/.env` is ignored by the compose runtime and replaced with the internal Docker Mongo address.

Optional root-shell overrides:

```env
PRODAGENTIC_PORT=8080
MONGO_DB=content_engine
APP_WORKSPACE_ID=legacy-default
SCHEDULER_ENABLED=true
PRODAGENTIC_COOKIE_SECURE=false
PRODAGENTIC_COOKIE_SAMESITE=lax
```

For local HTTP, `COOKIE_SECURE=false` is intentional. When this compose stack is placed behind HTTPS, set it to `true`.

## Start

From repository root:

```bash
docker compose up --build -d
```

Inspect:

```bash
docker compose ps
docker compose logs -f
```

Health:

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
```

## Stop

Keep data:

```bash
docker compose down
```

Destroy Mongo + rendered-asset volumes too:

```bash
docker compose down -v
```

## Security boundary

- Only `gateway` publishes a host port.
- MongoDB is not host-exposed.
- FastAPI is not host-exposed.
- Next.js is not host-exposed.
- `backend/.env` is excluded by `.dockerignore`.
- `/docs` and `/openapi.json` are blocked at the gateway.
- `/api/*` remains protected by prodAgentic's signed HttpOnly session and CSRF middleware.
- The frontend is built with a relative API origin (`NEXT_PUBLIC_API_URL=/`), so browser traffic remains same-origin through the gateway.

## Persistence

Named volumes:

```text
prodagentic_mongo_data
prodagentic_render_assets
```

This removes the ephemeral-render problem for the Docker deployment path without changing the current application storage contract.

## Not claimed

This is a single-host Docker deployment topology. It does not itself provide multi-node failover, managed database backups, TLS termination, or horizontal scheduler coordination.
