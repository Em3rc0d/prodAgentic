# Mining Site — Content Intelligence

Purpose: preserve evidence that justifies or falsifies design decisions.

## Rule

Every quarry must separate:

- **OBSERVED** — directly present in repository/runtime/test evidence.
- **INFERRED** — reasonable conclusion from observations, not yet proven by implementation/runtime.
- **PROPOSED** — intended future behavior.
- **REJECTED** — deliberately excluded design.
- **UNKNOWN** — not proven and must not be represented as fact.

A quarry is not marketing copy. It is engineering evidence.

## Quarry index

- `quarry-01-current-lifecycle.md` — authoritative existing ContentRun/approval/schedule/publication behavior.
- `quarry-02-memory-gap.md` — what duplicate protection currently proves and what semantic memory does not exist yet.
- `quarry-03-source-grounding-gap.md` — current research/context behavior and grounding gap.
- `quarry-04-visual-intelligence-gap.md` — current cinematic-metaphor visual prompt behavior and proposed intent layer.
- `quarry-05-scale-cost-boundary.md` — architecture constraints for 100-1000+ users and what must be measured.
- `quarry-06-foundation-build.md` — workspace foundation and deterministic content identity build evidence.
- `quarry-07-memory-persistence.md` — deterministic workspace-scoped memory persistence and real Mongo index evidence.
- `quarry-08-lifecycle-memory.md` — review/edit/approval/publication memory integration, failure discovery and CI-MEM-03A certification.

## Evidence update protocol

After implementation/testing, append or create an `Observed after build` evidence record with:

- branch/commit,
- exact test names or suite receipts,
- observed result,
- known limitation,
- verdict (`PASS`, `PARTIAL`, `FAIL`, `UNKNOWN`).

Do not overwrite pre-build observations; preserve the evolution, including failed gates that exposed real defects.