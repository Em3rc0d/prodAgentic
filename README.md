# prodAgentic

prodAgentic is a governed agentic content-production system. It plans, produces, validates, reviews, stores, schedules, publishes, and learns from content for multiple editorial identities while keeping human authority explicit.

## Branch authority

```text
main
  └─ stable / certified product authority

developer
  └─ integration authority for the next product line

temporary audit/candidate branch
  └─ allowed only for an explicit certification PR; never product authority by itself
```

Ordinary work uses `main` + `developer`. A temporary audit branch may exist when it is explicitly bound to a certification PR and protected branches are intentionally left untouched. In every case, a release candidate is an **exact immutable SHA**, never a branch name.

## Current state

- `main@790f1e86312e13f4b14f1320db5d83f94ed8a97e` — MK1-R3 stable/certified authority.
- `developer@61bf7f93b37b00f3315c3f710d8005fed977e672` — frozen R4 integration baseline while the independent R4.1 audit is open.
- PR #69 (`r4.1-reliability-evidence-authority` → `developer`) — active R4.1 pre-UAT certification line. Its exact head SHA is the only candidate identity.
- R4 remains **NOT CERTIFIED** until exact-head automated gates (including dependency audits), fresh real-provider Profile-v2 ×4 UAT, human 4/4 editorial approval, authorized merge, and exact-main post-certification all pass.

Canonical development entry: [`mk1/build/WORK_START_HERE.md`](mk1/build/WORK_START_HERE.md).

Canonical MK1 status: [`mk1/STATUS.md`](mk1/STATUS.md).

## MK1-R4 design

R4 closes the gap between a technically governed pipeline and a system that can produce complete, profile-driven, publishable editorial packages with real visual output.

Its authority model is a reciprocal validation graph:

```text
ProfileVersion
  ↕
CreativeBrief
  ↕
CandidatePool / EditorialMemory
  ↕
ContentPlan
  ↕
ResearchPack
  ↕
ContentSpec
  ↕
EditorialGate
  ↕
VisualSpec
  ↕
Owned source assets
  ↕
Rendered assets
  ↕
Visual QA
  ↕
Human review
  ↕
Approval bundle
  ↕
Export / publication
  ↕
Analytics / learning
  ↕
next planning cycle
```

Machine-readable graph: `mk1/build/r4/CERTIFICATION_GRAPH.json`.

Structural verifier:

```bash
python scripts/verify_r4_cert_graph.py
```

The verifier checks graph structure only. Product quality, supply-chain provenance, real-provider behavior and release certification remain separate blocking gates.

## Documentation method

MK1 follows:

```text
brainstorming → design → architecture → plan → build → test → certification → learning
```

Supporting evidence is organized under `mining-site/` and scoped investigations under `quarries/`.

When documents conflict:

```text
accepted ADR / invariant
        >
architecture contract
        >
design contract
        >
plan
        >
build note
        >
brainstorming / quarry finding
```

Certification receipts and exact-SHA evidence determine whether a release actually crossed its gates.
