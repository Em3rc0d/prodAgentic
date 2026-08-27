# prodAgentic

**Trusted agentic content production for LinkedIn.**

prodAgentic turns an idea into a reviewable, approval-bound LinkedIn publication workflow. It combines specialized AI stages with durable lifecycle state, reusable content profiles, human approval, scheduling, OAuth-authorized publishing, duplicate prevention and publication evidence.

## What Commercial V1 does

```text
Idea / brief
  -> research
  -> writing
  -> editing
  -> optional visual
  -> durable ContentRun
  -> human review
  -> immutable approval
  -> schedule or publish
  -> LinkedIn receipt
  -> exact Content Memory
```

The product is intentionally LinkedIn-first. It does not claim autonomous publication, semantic memory, analytics-driven learning, multi-channel distribution or multi-tenant SaaS in Commercial V1.

## Trust boundaries

- AI output is not publication authority.
- Only explicit human approval creates a publishable bundle.
- Approved text and visual evidence are cryptographically bound.
- OAuth is the normal LinkedIn authority; static credentials are disabled in production.
- Exact approved text is deduplicated per LinkedIn publishing identity.
- Ambiguous external publication outcomes require reconciliation rather than automatic replay.
- ContentRun is authoritative lifecycle state; Content Memory is an advisory projection.
- Durable generation fails closed when its ContentRun cannot be persisted.

## Run the complete stack

See [`docs/DOCKER_ONE_COMMAND.md`](docs/DOCKER_ONE_COMMAND.md).

The repository includes a single-host Docker topology with Next.js, FastAPI, MongoDB 7 and an nginx same-origin gateway. Production use requires an external trusted HTTPS/TLS boundary and the production environment contract documented there.

## Commercialization status

The first commercial mode is an **assisted private pilot**, not anonymous self-service SaaS. The product operator provisions the deployment, configures the workspace, verifies OAuth and performs the release checklist with the customer/operator before production use.

See [`docs/COMMERCIAL_V1.md`](docs/COMMERCIAL_V1.md) for the launch contract and acceptance gates.

## Runtime evidence without another LinkedIn post

An operator can validate an already-connected LinkedIn identity and an already-published ContentRun without creating another external side effect:

```bash
cd backend
python tools/release_receipt.py --run-id <published-run-id>
```

The receipt intentionally excludes access tokens, OAuth codes/state, cookies, secrets, plaintext content and raw member identifiers.

## Policies

- [`PRIVACY.md`](PRIVACY.md)
- [`TERMS.md`](TERMS.md)

## Development

The exact release candidate must pass the repository CI gates on one commit SHA: backend tests/audits, frontend tests/audits/build, browser certification and complete Docker-stack certification. A green historical run from another SHA is not release evidence.
