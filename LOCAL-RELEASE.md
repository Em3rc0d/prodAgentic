# Local release candidate

## Prerequisites

Docker Engine or Docker Desktop with Compose v2.24.4+, Git, and available loopback
ports 3000, 8000 and 27017. First build needs internet to download dependencies and
container images. Certification of this candidate is deferred to Jett.

## Environment setup

No environment file is required for the local journey. Optional overrides:
`cp .env.docker.example .env`. Never commit `.env` or generated credentials.
Default login: `admin` / `local-docker-password-change-me`.
Tenant bootstrap is automatic; create a Profile through the guided UI.

Default mode uses the existing deterministic local agents. It needs no Gemini key
or cloud service after installation. MongoDB, Chromium rendering, QA, approval and
PNG/ZIP export are real. The generated copy is explicitly demo content.
ProfileVersion, QA and Approval hash inputs retain exact timestamp precision.
For disposable data made by older candidates, use a new Profile or accept a new
Profile version before planning: lost timestamp precision cannot be reconstructed
by changing a stored digest. Historical records are not rewritten.

## How to start

From the repository root on `mk1-r2-local-release-stabilization`:

```bash
docker compose up --build -d --wait
```

Create Profile → Create batch (choose Carousel under optional constraints) →
Review → Approve → Download manual package. The ZIP includes separate PNGs,
manifest and metadata bound to the exact Approval. Downloads go to your browser's
configured download folder. Failed stages show their error; retry unfinished work
resumes from its persisted revision. A failed agent run without a revision requires
a new batch; an in-flight request must finish before retrying.

For the optional **local-production-like** configuration with strict production
settings, real secure cookies and local TLS:

```bash
docker compose down
docker compose -p prodagentic-production-like -f docker-compose.yml -f docker-compose.local-production.yml up --build -d --wait
docker compose -p prodagentic-production-like -f docker-compose.yml -f docker-compose.local-production.yml cp local-tls:/data/caddy/pki/authorities/local/root.crt ./local-root.crt
```

Trust that locally generated CA in your OS/browser to open both HTTPS origins.
This is the only mode requiring local certificate trust. Its data uses a separate
Compose project. It intentionally disables demo agents: set `GEMINI_API_KEY` in
`.env` to generate text in this mode. Without it the application starts, but provider
readiness explicitly reports `Missing API Key`; Profile/Batch and existing Review
remain available. The default local mode above supplies the cloud-free journey.

## Local URL

Default: **http://127.0.0.1:3000** (backend: http://127.0.0.1:8000).
Use the same hostname for both browser and API so session cookies work.
Production-like: **https://localhost:3000** (backend: https://localhost:8000).
`/health/live` reports process liveness; `/health/ready` reports database/provider
readiness. MongoDB and AssetStore use named volumes; they survive ordinary stops.

## How to stop

```bash
docker compose down
```

For production-like mode use the same project and file options from its start
command followed by `down`. Remove the local CA from your trust store when finished
with that mode. Neither command deletes stored content.

## How to reset disposable local data

Only when you deliberately want to delete this local project's Profiles, content,
approvals and assets:

```bash
docker compose down --volumes
```

For production-like data, use its project and file options with `down --volumes`.
That also removes its local CA; delete `local-root.crt` and remove its old trust.

## Known optional integrations

- `PRODAGENTIC_DEMO_MODE=false` plus `GEMINI_API_KEY` selects real model providers.
- LinkedIn OAuth and n8n are optional; neither is needed for local manual export.
- Redis is required only for background job transport. The synchronous local
  produce/QA/approve/export flow does not use it. To add it, start with
  `docker compose -f docker-compose.yml -f docker-compose.s9.yml up --build -d --wait`.
- WSL private-network overrides remain documented in `.env.docker.example`.
- `docker-compose.cutover.yml` remains a CI production-smoke configuration with
  synthetic credentials and example origins; it is not the browser start command.
