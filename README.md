# prodAgentic

prodAgentic is a governed agentic content-production system for planning, producing, validating, reviewing, storing, exporting/publishing and learning from content across multiple editorial identities while keeping the operator in control.

## Repository authority

The repository uses only two active authority branches:

```text
main       stable / certified line
developer  active design + implementation line
```

Current anchors:

```text
main
790f1e86312e13f4b14f1320db5d83f94ed8a97e
MK1-R3 certified stable authority

developer
active MK1-R4 design / implementation / hardening authority
```

Do not create long-lived slice, feature, docs, fix, candidate-shadow or certification-shadow branches. Engineering state belongs in the MK folder/evidence graph; integration state belongs in `main` and `developer`.

Canonical policy: [`mk1/build/REPOSITORY_HYGIENE.md`](mk1/build/REPOSITORY_HYGIENE.md).

## Current product state

```text
MK1-R3   CERTIFIED / MERGED on main
MK1-R4   IMPLEMENTED / DESIGN + HARDENING OPEN on developer
```

R4 is not certified merely because its implementation exists. It becomes releasable only after an exact `developer` candidate SHA passes the complete required gates and the exact merged `main` passes post-merge certification.

## Current product flow

```text
Profile / immutable ProfileVersion
        ↓
Batch planning + Editorial Memory + Novelty
        ↓
ContentPlan / ResearchPack
        ↓
ContentSpec
        ↓
Editorial Review + Publishability
        ↓
DesignProfile / VisualSpec
        ↓
Generated or deterministic visual source assets
        ↓
Chromium render + owned final assets
        ↓
QA + recovery
        ↓
Human review + approval
        ↓
Manual export / bounded distribution
        ↓
Persistence + restart recovery
```

The active R4 design extends this graph toward stronger creative production, provenance, traceability, validation and future learning loops without changing the certified R3 boundary until R4 itself is certified.

## Run locally

See [`LOCAL-RELEASE.md`](LOCAL-RELEASE.md) first.

Default Docker path:

```bash
git switch developer
git pull
docker compose up --build
```

Then open:

```text
http://localhost:3000
```

For WSL native Docker where Windows localhost forwarding is unreliable, use [`docs/WSL_NATIVE_DOCKER.md`](docs/WSL_NATIVE_DOCKER.md).

Other runbooks:

- [`docs/DOCKER_LOCAL.md`](docs/DOCKER_LOCAL.md)
- [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md)
- [`mk1/test/LOCAL_ACCEPTANCE.md`](mk1/test/LOCAL_ACCEPTANCE.md)

## MK engineering method

Each MK follows the same internal structure:

```text
brainstorming/
design/
arch/
plan/
build/
test/
mining-site/
quarries/
```

The delivery flow is:

```text
brainstorming → design → architecture → plan → build → test
```

`mining-site` and `quarries` carry research, source provenance, extraction and evidence. Important decisions should be closed before implementation; open architectural/product nodes are not hidden behind code.

## Documentation authority

When active MK documents conflict:

```text
accepted ADR / invariant
        >
architecture contract
        >
design contract
        >
plan
        >
build record
        >
brainstorming / quarry finding
```

Certification receipts plus `mk1/STATUS.md` determine whether a release actually crossed its gates.

## Promotion law

```text
developer
   ↓ freeze exact candidate SHA
   ↓ full required gates
   ↓ no mutation after candidate green
   ↓ PR developer -> main
main
   ↓ exact-main post-certification
   ↓ final release certificate
```

A failed or mutated candidate is superseded. It is never relabeled as certified.
