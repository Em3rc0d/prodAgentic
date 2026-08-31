# prodAgentic

**Trusted agentic content production for LinkedIn.**

> **prodAgentic does not invent a better story. It finds the best story the evidence already contains.**

prodAgentic turns real knowledge, decisions and experience into reviewable LinkedIn content while preserving explicit human authority over factual Grounding and publication.

## What Commercial V1 does

```text
Evidence / brief
  -> SourcePacket
  -> research / writing / editing
  -> claim-level Grounding assessment
  -> deterministic Grounding policy
  -> explicit human Grounding verification
  -> optional visual
  -> durable ContentRun
  -> human content review
  -> immutable approval
  -> schedule or publish
  -> LinkedIn receipt
  -> exact Content Memory
```

Commercial V1 is intentionally LinkedIn-first and assisted. It does not claim autonomous semantic truth determination, autonomous publication, analytics-driven learning, multi-channel distribution or multi-tenant SaaS.

## Value + trust

prodAgentic treats content quality and factual integrity as separate requirements:

```text
VALUE ENGINE
Does this deserve attention?

TRUST ENGINE
Can we defend what it claims?
```

A generic but truthful post is a product-quality failure. A compelling post that fabricates significance is a trust failure.

## Trust boundaries

- AI may propose claims and evidence links; it does not make itself factual authority.
- `GROUNDING-01`: no unsupported factual claim may reach `APPROVED`.
- Contradicted or insufficiently supported factual claims block the Grounding policy.
- Supported inferences remain explicit and visible to the reviewer.
- Grounding is bound to the exact final-content SHA-256.
- A text edit invalidates the previous Grounding assessment and human verification.
- A deterministic Grounding `PASS` is not enough: an explicit human `VERIFIED` review is required.
- Approval recomputes Grounding policy rather than trusting a cached gate value.
- Only explicit human content approval creates a publishable bundle.
- Approved text, Grounding provenance digests and visual evidence are cryptographically bound.
- OAuth is the normal LinkedIn authority; static credentials are disabled in production.
- Exact approved text is deduplicated per LinkedIn publishing identity.
- Ambiguous external publication outcomes require reconciliation rather than automatic replay.
- ContentRun is authoritative lifecycle state; Content Memory is an advisory projection.
- Durable generation fails closed when its ContentRun cannot be persisted.

See [`docs/content-intelligence/design/GROUNDING-01.md`](docs/content-intelligence/design/GROUNDING-01.md) for the evidence-first trust contract.

## Local qualification before deployment

Deployment is not the next definition of success. Before Commercial V1 is treated as valuable, prodAgentic is qualified locally against real evidence using a Golden Content Set.

The local evaluation must answer two independent questions:

1. **Would we genuinely publish this?**
2. **Can every meaningful factual claim be defended from the supplied evidence?**

The next Content Intelligence slice adds semantic claim extraction, evidence matching, contradiction detection, rewrite/soften behavior and blind editorial evaluation on real project material.

## Run the complete stack

See [`docs/DOCKER_ONE_COMMAND.md`](docs/DOCKER_ONE_COMMAND.md).

The repository includes a single-host Docker topology with Next.js, FastAPI, MongoDB 7 and an nginx same-origin gateway. Production use requires an external trusted HTTPS/TLS boundary and the production environment contract documented there.

## Commercialization status

The first commercial mode is an **assisted private pilot**, not anonymous self-service SaaS. The product operator provisions the deployment, configures the workspace, verifies Grounding and OAuth, and performs the release checklist with the customer/operator before production use.

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
