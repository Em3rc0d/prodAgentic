# prodAgentic Frontend

Next.js frontend for prodAgentic.

The active MK1 product surface is currently certified through:

```text
S0 — MK1 shell / bootstrap tenant
S1 — Profile V2
S2 — Batch + Editorial Memory + Novelty
```

For the complete operator setup, use [`../docs/LOCAL_DEVELOPMENT.md`](../docs/LOCAL_DEVELOPMENT.md).

## Toolchain

Canonical CI uses:

```text
Node.js 24
npm ci
Next.js 16.3.3
React 19.2.4
```

## Local environment

Create `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MK1_SHELL=true
NEXT_PUBLIC_MK1_PROFILE_V2=true
NEXT_PUBLIC_MK1_BATCH_PLANNING=true
```

The matching backend flags must also be enabled. Frontend flags do not create backend authority.

## Install and run

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

## Product UX boundary

MK1 is designed as a low-friction cockpit:

- normal users should not configure models or agents;
- important complexity is hidden by default but inspectable on demand;
- Profile setup requires proposal review before immutable acceptance;
- Create/Batch planning exposes concise status first and planning evidence progressively;
- honest partial Batch completion is preferred over filler content;
- S0→S2 must not trigger S3 production or external publication.

## Local acceptance

After both frontend/backend are running, execute:

```text
../mk1/test/LOCAL_ACCEPTANCE.md
```

Do not treat visual rendering alone as a PASS. The checklist includes persistence, restart, ProfileVersion freeze, Editorial Memory, feature flags and fail-closed boundaries.
