# prodAgentic Backend

FastAPI backend for prodAgentic.

The active MK1 product baseline is currently certified through S2.

## Preferred full-stack local path

From the repository root:

```bash
docker compose up --build
```

Compose reuses the existing `backend/Dockerfile`, starts Mongo first, waits for Mongo health, then starts the backend with:

```text
MONGO_URI=mongodb://mongo:27017/prodagentic_local
```

The backend is published only on:

```text
127.0.0.1:8000
```

See [`../docs/DOCKER_LOCAL.md`](../docs/DOCKER_LOCAL.md).

For manual/non-Docker setup, use [`../docs/LOCAL_DEVELOPMENT.md`](../docs/LOCAL_DEVELOPMENT.md).

## Toolchain

Canonical CI uses:

```text
Python 3.11
MongoDB 7
```

Production dependencies are locked with hashes in:

```text
requirements.lock
```

Test/development-only dependencies are in:

```text
requirements-dev.txt
```

## Local setup without Compose

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install exact production dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements.lock
```

For tests:

```bash
python -m pip install -r requirements-dev.txt
```

Copy the local environment template:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

## MK1 S0→S2 feature flags

For the current local acceptance:

```dotenv
MK1_ENABLED=true
MK1_PROFILE_V2=true
MK1_BATCH_PLANNING=true
```

Use local Mongo:

```dotenv
MONGO_URI=mongodb://127.0.0.1:27017/prodagentic_local
MONGO_DB=prodagentic_local
PRODAGENTIC_DEPLOYMENT_KEY=local-installation
```

For realistic operator acceptance, keep auth enabled and configure strong local-only credentials:

```dotenv
PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=<at-least-12-characters>
PRODAGENTIC_SESSION_SECRET=<at-least-32-random-characters>
PRODAGENTIC_COOKIE_SECURE=false
PRODAGENTIC_COOKIE_SAMESITE=lax
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
FRONTEND_URL=http://localhost:3000
```

Never commit `.env`.

## Start manually

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Liveness:

```bash
curl http://127.0.0.1:8000/health/live
```

Full readiness:

```bash
curl http://127.0.0.1:8000/health/ready
```

`/health/ready` includes broader runtime/provider readiness. Missing `GEMINI_API_KEY` may therefore make readiness fail even when the S0→S2 application surface can still be exercised. Preserve the distinction in test evidence.

## Docker health boundary

Compose deliberately uses `/health/live` rather than `/health/ready` as the backend container healthcheck. The local S0→S2 planning surface does not require the future S3 model-generation cell, while readiness includes provider availability.

## Tests

```bash
python -m compileall .
python -m pytest -q
```

Canonical CI also runs the suite against a real MongoDB 7 service, builds/smokes the production backend image, and the dedicated Docker Compose workflow starts the complete Mongo + backend + frontend stack.

## Current MK1 authority

S0:

- server-owned bootstrap tenant;
- tenant-scoped repository boundary;
- additive/idempotent migration;
- gated MK1 shell.

S1:

- low-friction Profile V2 setup;
- proposal before acceptance;
- immutable ProfileVersion;
- exact digests and restart recovery;
- structural credential/OAuth separation.

S2:

- first-class Batch planning;
- Editorial Memory;
- deterministic novelty/cooldown evaluation;
- diversity-aware selection;
- immutable ContentPlanV1 evidence;
- Batch-last commit boundary.

S2 must not invoke S3 Research/Writer/Editor/Visual or publish externally.

## Operator acceptance

After the stack is running, follow:

```text
../mk1/test/LOCAL_ACCEPTANCE.md
```
