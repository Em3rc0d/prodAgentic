# prodAgentic — Local Development Runbook

This is the canonical operator runbook for bringing the current MK1 product baseline up locally.

It is intentionally scoped to the exact product state certified on `main` through **S2 — Batch + Editorial Memory + Novelty**. It does not pretend S3+ exists.

## 1. Known-good repository baseline

Before testing, synchronize to `main` and verify the expected baseline:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
```

Expected certified S2 merge baseline at the time this runbook was written:

```text
002177e90431d6009498a88cc6eb20efc46e14b3
```

If `main` has moved, do not assume this document certifies the newer SHA. Check `mk1/STATUS.md` first.

The exact baseline above passed:

```text
backend-test        PASS
frontend-test       PASS
UI-01-CERT browser PASS
```

in post-merge CI run `33982022917`.

## 2. Supported local toolchain

The canonical CI toolchain is the safest local reference:

```text
Python 3.11
Node.js 24
MongoDB 7
npm with package-lock (`npm ci`)
pip with hashed `backend/requirements.lock`
```

Recommended local environment:

- Git;
- Python 3.11;
- Node.js 24;
- Docker Desktop / Docker Engine for MongoDB 7, or a native MongoDB 7 instance;
- two terminals for backend/frontend;
- a modern Chromium-based browser.

## 3. Start MongoDB

### Docker option

If port `27017` is free:

```bash
docker run -d \
  --name prodagentic-mongo \
  -p 27017:27017 \
  mongo:7
```

Verify:

```bash
docker ps --filter name=prodagentic-mongo
docker exec prodagentic-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok'
```

Expected Mongo response:

```text
1
```

If the container already exists:

```bash
docker start prodagentic-mongo
```

### Native Mongo option

Use a local MongoDB 7 service listening on `127.0.0.1:27017` and set the same URI shown below.

## 4. Backend setup

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment.

Linux/WSL/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the exact locked production dependency graph:

```bash
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements.lock
```

For running the test suite as well:

```bash
python -m pip install -r requirements-dev.txt
```

Create the local environment file:

Linux/WSL/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## 5. Backend environment for MK1 S0→S2

Edit `backend/.env`.

Minimum product flags for the current MK1 acceptance surface:

```dotenv
APP_DEFAULT_LANGUAGE=es
LANGUAGE_MIN_CONFIDENCE=0.6
LANGUAGE_MIN_MARGIN=0.2
IMAGE_RENDER_ENABLED=false

MONGO_URI=mongodb://127.0.0.1:27017/prodagentic_local
MONGO_DB=prodagentic_local
PRODAGENTIC_DEPLOYMENT_KEY=local-installation

MK1_ENABLED=true
MK1_PROFILE_V2=true
MK1_BATCH_PLANNING=true

PRODAGENTIC_AUTH_ENABLED=true
PRODAGENTIC_ADMIN_USER=admin
PRODAGENTIC_ADMIN_PASSWORD=replace-this-with-a-local-password-at-least-12-characters
PRODAGENTIC_SESSION_SECRET=replace-this-with-a-random-local-secret-at-least-32-characters
PRODAGENTIC_SESSION_TTL_SECONDS=43200
PRODAGENTIC_COOKIE_SECURE=false
PRODAGENTIC_COOKIE_SAMESITE=lax

CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
FRONTEND_URL=http://localhost:3000
```

### Gemini key boundary

The current backend knows about the model provider through `GEMINI_API_KEY`.

For a **full runtime readiness** check, configure a valid key:

```dotenv
GEMINI_API_KEY=<your-real-local-development-key>
```

S0/S1/S2 local acceptance itself must not invoke the future S3 production cell. Therefore Profile V2 and Batch/Novelty acceptance should not depend on a model-generation call. However, `/health/ready` is a broader system readiness signal and may correctly remain non-ready when no viable model provider is configured.

Do not commit `.env` or any secret.

### LinkedIn boundary

LinkedIn is **not part of the S0→S2 acceptance pass**. Do not create a LinkedIn post just to test these slices.

You may leave LinkedIn unconfigured unless you intentionally test the existing MK0 integration separately. If configured, keep OAuth secrets only in `.env`.

## 6. Start the backend

With the virtual environment active and while inside `backend/`:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal, verify liveness:

```bash
curl http://127.0.0.1:8000/health/live
```

The endpoint must return a successful response.

If a valid model provider is configured, also verify:

```bash
curl http://127.0.0.1:8000/health/ready
```

A `ready` failure with a missing provider is not equivalent to a backend crash; inspect the response/logs and preserve the distinction.

## 7. Frontend setup

Open a second terminal from the repository root:

```bash
cd frontend
npm ci
```

Create `frontend/.env.local` with:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MK1_SHELL=true
NEXT_PUBLIC_MK1_PROFILE_V2=true
NEXT_PUBLIC_MK1_BATCH_PLANNING=true
```

Then start Next.js:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

The frontend code defaults to `http://localhost:8000` in development when no API URL is supplied, but the explicit `.env.local` above is preferred because it makes the acceptance configuration auditable.

## 8. Authentication

With `PRODAGENTIC_AUTH_ENABLED=true`, sign in using the local admin credentials configured in `backend/.env`.

The frontend uses the backend session endpoint:

```text
POST /api/auth/login
```

The session cookie is HTTP-only and the backend supplies the CSRF token used by state-changing requests. Keep `PRODAGENTIC_COOKIE_SECURE=false` for plain HTTP localhost development; production must use the secure-cookie boundary.

For a narrow diagnostic pass only, CI sometimes runs with auth disabled. Operator acceptance should prefer auth enabled so the browser/session boundary is exercised.

## 9. Current MK1 routes to exercise

The primary current surfaces are:

```text
/profiles    S1 Profile V2
/create      S2 Batch + Memory + Novelty
```

The full acceptance sequence is defined in:

```text
mk1/test/LOCAL_ACCEPTANCE.md
```

## 10. Optional local regression tests

### Backend

With Mongo running and dev dependencies installed:

```bash
cd backend
python -m compileall .
python -m pytest -q
```

The canonical CI also exercises a real Mongo 7 service and production Docker image smoke test.

### Frontend

```bash
cd frontend
npm run lint
npm test
```

Development server:

```bash
npm run dev
```

Production-style build verification requires an explicit API origin:

Linux/WSL/macOS:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 \
NEXT_PUBLIC_MK1_SHELL=true \
NEXT_PUBLIC_MK1_PROFILE_V2=true \
NEXT_PUBLIC_MK1_BATCH_PLANNING=true \
npm run build
```

PowerShell:

```powershell
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
$env:NEXT_PUBLIC_MK1_SHELL="true"
$env:NEXT_PUBLIC_MK1_PROFILE_V2="true"
$env:NEXT_PUBLIC_MK1_BATCH_PLANNING="true"
npm run build
```

## 11. Clean local reset

Use this only when you intentionally want to destroy the local test database.

Docker Mongo container + data inside the container:

```bash
docker rm -f prodagentic-mongo
```

Then recreate it using the command in section 3.

If you use a persistent Docker volume or Mongo Atlas, deleting the container does **not** necessarily delete the database. Treat persistence explicitly.

Do not delete production/remote data as part of a local reset.

## 12. Troubleshooting map

### Frontend loads but API requests fail

Check:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
CORS_ALLOWED_ORIGINS includes http://localhost:3000 and http://127.0.0.1:3000
backend /health/live succeeds
```

### Login succeeds but state-changing actions fail

Check browser cookies and backend logs. The app requires the session/CSRF boundary; do not bypass it by editing frontend code for the acceptance test.

### Profile or Batch routes return 404

Verify all relevant flags are enabled on **both** sides:

```text
backend:
  MK1_ENABLED=true
  MK1_PROFILE_V2=true
  MK1_BATCH_PLANNING=true

frontend:
  NEXT_PUBLIC_MK1_SHELL=true
  NEXT_PUBLIC_MK1_PROFILE_V2=true
  NEXT_PUBLIC_MK1_BATCH_PLANNING=true
```

Restart both servers after changing environment variables.

### Mongo connection fails

Verify:

```bash
docker ps --filter name=prodagentic-mongo
docker exec prodagentic-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok'
```

and confirm `MONGO_URI` points to the same host/port.

### Batch returns fewer items than requested

This can be **correct S2 behavior**. The novelty engine is fail-closed: it may produce a partial Batch instead of relaxing repetition standards. Record the selected/requested counts and inspect the progressively disclosed planning evidence.

### `/health/ready` fails but S0→S2 UI is usable

Check whether `GEMINI_API_KEY` is configured. Liveness, S0→S2 acceptance, and full provider readiness are distinct gates; report exactly which one failed.

## 13. Stop the local stack

Stop frontend/backend with `Ctrl+C` in their terminals.

Stop Mongo:

```bash
docker stop prodagentic-mongo
```

The next run can restart it with:

```bash
docker start prodagentic-mongo
```

## 14. Evidence to report back

When the local pass is complete, report:

```text
git SHA
OS / WSL or native Windows
Python version
Node version
Mongo version
backend /health/live
backend /health/ready (and whether a provider key was configured)
login PASS/FAIL
Profile V2 PASS/FAIL
Profile update/history PASS/FAIL
Create Batch PASS/FAIL
requested vs selected count
planning evidence visible after disclosure PASS/FAIL
browser console errors, if any
backend errors, if any
screenshots for any visual/UX defect
```

Use `mk1/test/LOCAL_ACCEPTANCE.md` as the authoritative checklist and fail closed: a defect is evidence to fix, not a reason to redefine the expected behavior during the test.
