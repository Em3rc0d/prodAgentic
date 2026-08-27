# prodAgentic — one-command Docker stack

Status: Commercial V1 reconciliation candidate.

## Goal

Run the complete prodAgentic stack locally, or behind an external TLS terminator, after secrets are present:

```bash
docker compose up --build -d
```

Local default:

```text
http://localhost:8080
```

Only nginx is exposed to the host. Next.js, FastAPI and MongoDB remain on the internal Docker network.

## Topology

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

The scheduler runs in the FastAPI container. Mongo data and the complete configured prodAgentic asset root use named Docker volumes.

## Secrets

The stack intentionally reuses `backend/.env`. It is git-ignored and excluded from the backend Docker context. Never commit it.

Minimum local runtime values:

```env
GEMINI_API_KEY=<your key>
APP_DEFAULT_LANGUAGE=es
PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=<at least 12 characters>
PRODAGENTIC_SESSION_SECRET=<at least 32 random characters>
PRODAGENTIC_LINKEDIN_TOKEN_KEY=<independent random secret of at least 32 characters>
LINKEDIN_CLIENT_ID=<your LinkedIn app id>
LINKEDIN_CLIENT_SECRET=<your LinkedIn app secret>
LINKEDIN_API_VERSION=202607
```

`MONGO_URI`, asset storage, the same-origin gateway flag and static LinkedIn fallback are runtime-controlled by Compose. Static LinkedIn credentials remain disabled.

## Local HTTP mode

Default Compose values are intentionally development-only:

```env
PRODAGENTIC_ENV=development
PRODAGENTIC_PUBLIC_ORIGIN=http://localhost:8080
PRODAGENTIC_COOKIE_SECURE=false
PRODAGENTIC_COOKIE_SAMESITE=lax
LINKEDIN_REDIRECT_URI=http://localhost:8080/api/integrations/linkedin/callback
```

Register that callback in the LinkedIn developer application before attempting local OAuth.

## Public production mode

The nginx container in this repository does **not** terminate TLS. Put the stack behind a trusted HTTPS reverse proxy/load balancer and set, for example:

```env
PRODAGENTIC_ENV=production
PRODAGENTIC_PUBLIC_ORIGIN=https://app.example.com
PRODAGENTIC_COOKIE_SECURE=true
PRODAGENTIC_COOKIE_SAMESITE=lax
LINKEDIN_REDIRECT_URI=https://app.example.com/api/integrations/linkedin/callback
```

The backend production validator fails closed unless:

- auth is enabled;
- cookies are Secure;
- the explicit same-origin gateway uses `SameSite=Lax`;
- the frontend/CORS origin is canonical HTTPS and restricted to the same origin;
- the asset root is absolute and durable;
- static LinkedIn credential fallback is disabled.

If the same-origin flag is not used, the existing split frontend/backend production contract remains unchanged and requires `SameSite=None`.

## Start and inspect

```bash
docker compose up --build -d
docker compose ps
docker compose logs --no-color --tail=200
```

Health:

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
```

`/health/live` proves process liveness. `/health/ready` is the stronger product-readiness gate and requires database/config/model readiness.

## Stop

Preserve data:

```bash
docker compose down
```

Destroy Mongo and asset volumes:

```bash
docker compose down -v
```

## Security boundary

- only nginx publishes a host port;
- MongoDB, FastAPI and Next.js remain internal;
- `backend/.env` is excluded from image context;
- `/docs` and `/openapi.json` are blocked at the gateway;
- `/api/*` remains behind signed HttpOnly session + CSRF protection;
- frontend API calls use the explicit same-origin `/` build contract;
- production same-origin cookies are Secure + Lax;
- nginx adds anti-framing, MIME-sniffing, referrer, permissions and baseline CSP headers;
- OAuth/static-publication authority remains owned by the backend, never by the frontend.

## Persistence

Named volumes:

```text
prodagentic_mongo_data
prodagentic_render_assets
```

The asset volume is mounted at `/data/prodagentic`, and the backend uses `/data/prodagentic/assets` as its single authoritative asset root.

## Not claimed

This topology is single-host. It does not itself provide TLS termination, managed backups, multi-node failover, horizontal scheduler coordination or a distributed publication queue.
