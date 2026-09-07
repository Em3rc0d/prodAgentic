# prodAgentic — Docker Compose Local Stack

This is the preferred path for running the currently certified MK1 S0→S2 product surface on one machine.

## One-command start

From the repository root:

```bash
docker compose up --build
```

Then open:

```text
http://localhost:3000
```

Default local login:

```text
username: admin
password: local-docker-password-change-me
```

Those credentials are intentionally LOCAL-ONLY defaults. The Compose ports bind only to `127.0.0.1`. Change the credentials before using any non-test local data.

## Stack topology

```text
Browser
  |
  | http://localhost:3000
  v
frontend — Next.js 16 / Node 24
  |
  | browser-visible API origin: http://127.0.0.1:8000
  v
backend — FastAPI / Python 3.11
  |
  | mongodb://mongo:27017/prodagentic_local
  v
mongo — MongoDB 7
```

Host bindings:

```text
127.0.0.1:3000 -> frontend:3000
127.0.0.1:8000 -> backend:8000
127.0.0.1:27017 -> mongo:27017
```

The services are not exposed on all network interfaces by the checked-in local Compose contract.

## Health and startup order

Compose uses health-gated dependencies:

```text
Mongo healthy
   ↓
Backend /health/live healthy
   ↓
Frontend HTTP healthy
```

Useful commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mongo
```

Backend liveness from the host:

```bash
curl http://127.0.0.1:8000/health/live
```

Full readiness:

```bash
curl http://127.0.0.1:8000/health/ready
```

`/health/ready` is broader than the S0→S2 local acceptance surface. If `GEMINI_API_KEY` is not configured, full provider readiness may correctly remain false while Profile V2 and deterministic S2 Batch planning are still usable.

## Persistent local data

Compose creates two named volumes:

```text
prodagentic_mongo_data
prodagentic_assets
```

Normal shutdown preserves them:

```bash
docker compose down
```

Start again later:

```bash
docker compose up --build
```

The previous Mongo state and owned assets remain.

To intentionally destroy local Compose data:

```bash
docker compose down -v
```

Do not run the destructive form against a stack whose data you intend to keep.

## Optional environment overrides

The stack starts without an environment file.

For custom local credentials, a Gemini key, or deliberate testing of an optional integration, copy:

```bash
cp .env.docker.example .env.docker
```

PowerShell:

```powershell
Copy-Item .env.docker.example .env.docker
```

Then start with:

```bash
docker compose --env-file .env.docker up --build
```

`.env.docker` is git-ignored.

Common overrides:

```dotenv
GEMINI_API_KEY=
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=<local-password-at-least-12-characters>
PRODAGENTIC_SESSION_SECRET=<local-secret-at-least-32-characters>
PRODAGENTIC_DEPLOYMENT_KEY=local-docker-installation
```

Do not commit real keys or credentials.

## MK1 scope deliberately enabled

The checked-in Compose stack enables exactly the currently certified MK1 planning line:

```text
MK1_ENABLED=true
MK1_PROFILE_V2=true
MK1_BATCH_PLANNING=true
```

Frontend build-time flags are frozen into the local production-style Next.js image:

```text
NEXT_PUBLIC_MK1_SHELL=true
NEXT_PUBLIC_MK1_PROFILE_V2=true
NEXT_PUBLIC_MK1_BATCH_PLANNING=true
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

S3 is not enabled or invoked by this local stack.

## External side-effect boundary

For S0→S2 acceptance:

- image rendering is disabled;
- the scheduler is disabled;
- LinkedIn static fallback is disabled;
- LinkedIn client id, client secret and token-encryption key are empty by default;
- the LinkedIn integration therefore reports itself unconfigured until the operator deliberately supplies credentials;
- no LinkedIn post should be created;
- no external publication should occur;
- no S3 Research/Writer/Editor/Visual generation is required for Batch planning.

A side effect from `Generate next batch` is a FAIL.

## Frontend image

`frontend/Dockerfile` is a multi-stage Node 24 image:

```text
deps
  -> npm ci
builder
  -> Next production build
  -> npm prune --omit=dev
runner
  -> production dependencies + .next + public
  -> non-root node user
```

The browser-facing API origin is a build argument because `NEXT_PUBLIC_*` values are compiled into the Next.js client bundle.

Do not change the Compose build argument to `http://backend:8000`: that hostname is resolvable only inside the Docker network, not from the user's browser. The browser must use the host-published loopback endpoint.

## Backend image

The existing `backend/Dockerfile` remains the backend image authority. It installs the hash-locked production dependency graph and runs:

```text
uvicorn main:app --host 0.0.0.0 --port 8000
```

Compose overrides the Mongo URI to the internal service hostname:

```text
mongodb://mongo:27017/prodagentic_local
```

## Rebuild behavior

After source changes:

```bash
docker compose up --build
```

To force a clean rebuild:

```bash
docker compose build --no-cache
docker compose up
```

## Stop / restart

Stop while preserving data:

```bash
docker compose down
```

Restart:

```bash
docker compose up --build
```

Background mode:

```bash
docker compose up -d --build
```

Follow logs:

```bash
docker compose logs -f
```

## Troubleshooting

### Port already in use

Check ports 3000, 8000 and 27017. Stop any manually started Next/FastAPI/Mongo processes or another Compose stack using the same bindings.

### Frontend is healthy but API calls fail

Verify:

```bash
docker compose ps
curl http://127.0.0.1:8000/health/live
```

The frontend image is intentionally built with:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Backend does not become healthy

Inspect:

```bash
docker compose logs backend
docker compose logs mongo
```

Auth configuration requires a password of at least 12 characters and a session secret of at least 32 characters. The checked-in local defaults satisfy those constraints.

### `/health/ready` is not ready

If no `GEMINI_API_KEY` is configured, this can be expected. Use `/health/live` to distinguish a running backend from full provider readiness.

### LinkedIn says not configured

That is the expected S0→S2 local default. Do not add real OAuth credentials merely to pass the planning acceptance gate.

### I changed a `NEXT_PUBLIC_*` flag but nothing changed

Those values are build-time inputs. Rebuild the frontend image:

```bash
docker compose up --build
```

## Certification

The repository CI contains a dedicated Compose smoke gate that:

1. validates the Compose model;
2. builds backend and frontend images;
3. starts Mongo, backend and frontend with health-gated dependencies;
4. waits for all services to become healthy;
5. checks backend liveness;
6. checks frontend HTTP availability;
7. exercises the default local auth login boundary;
8. captures logs on failure;
9. destroys CI-only volumes after the run.

A green ordinary backend/frontend/browser CI is not substituted for this Compose gate. The one-command stack must pass on its own exact PR head.

## Product acceptance after startup

Once the stack is healthy, run the operator checklist in:

```text
mk1/test/LOCAL_ACCEPTANCE.md
```

The Docker stack changes how the product is started, not what qualifies as S0→S2 acceptance.
