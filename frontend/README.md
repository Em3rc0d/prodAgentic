# prodAgentic Frontend

Next.js frontend for prodAgentic.

The active MK1 product surface is currently certified through:

```text
S0 — MK1 shell / bootstrap tenant
S1 — Profile V2
S2 — Batch + Editorial Memory + Novelty
```

## Preferred full-stack local path

From the repository root:

```bash
docker compose up --build
```

Then open `http://localhost:3000`.

The Compose path builds this frontend from `frontend/Dockerfile`, starts Mongo + backend first through health-gated dependencies, and freezes the browser-visible API origin to `http://127.0.0.1:8000`.

See [`../docs/DOCKER_LOCAL.md`](../docs/DOCKER_LOCAL.md).

For manual/non-Docker setup, use [`../docs/LOCAL_DEVELOPMENT.md`](../docs/LOCAL_DEVELOPMENT.md).

## Toolchain

Canonical CI uses:

```text
Node.js 24
npm ci
Next.js 16.3.3
React 19.2.4
```

## Local environment without Compose

Create `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MK1_SHELL=true
NEXT_PUBLIC_MK1_PROFILE_V2=true
NEXT_PUBLIC_MK1_BATCH_PLANNING=true
```

The matching backend flags must also be enabled. Frontend flags do not create backend authority.

## Install and run manually

```bash
npm ci
npm run dev
```

Open:

```text
http://localhost:3000
```

Primary MK1 routes for the current acceptance pass:

```text
/profiles
/create
```

## Checks

```bash
npm run lint
npm test
```

Production-style build:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 \
NEXT_PUBLIC_MK1_SHELL=true \
NEXT_PUBLIC_MK1_PROFILE_V2=true \
NEXT_PUBLIC_MK1_BATCH_PLANNING=true \
npm run build
```

On PowerShell, set the same values through `$env:<NAME>` before `npm run build`.

The production build intentionally fails when `NEXT_PUBLIC_API_URL` is absent or is not a clean backend origin.

## Docker image contract

`frontend/Dockerfile` uses Node 24 multi-stage build layers:

```text
deps -> npm ci
builder -> npm run build -> npm prune --omit=dev
runner -> non-root node user + production Next runtime
```

`NEXT_PUBLIC_*` values are build-time inputs, so changing them requires rebuilding the image.

## Product UX boundary

MK1 is designed as a low-friction cockpit:

- normal users should not configure models or agents;
- important complexity is hidden by default but inspectable on demand;
- Profile setup requires proposal review before immutable acceptance;
- Create/Batch planning exposes concise status first and planning evidence progressively;
- honest partial Batch completion is preferred over filler content;
- S0→S2 must not trigger S3 production or external publication.

## Local acceptance

After the stack is running, execute:

```text
../mk1/test/LOCAL_ACCEPTANCE.md
```

Do not treat visual rendering alone as a PASS. The checklist includes persistence, restart, ProfileVersion freeze, Editorial Memory, feature flags and fail-closed boundaries.
