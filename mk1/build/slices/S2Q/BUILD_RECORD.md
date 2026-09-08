# S2-Q — Topic Authority + Product Honesty Hardening

Status: IMPLEMENTED / AWAITING EXACT-HEAD CERTIFICATION

## Objective

Close the operator-found defect where a Profile audience sentence could be promoted verbatim to `IdeaCandidateV1.topic`, producing structurally valid but editorially meaningless Batch plans. Make the Create UI state exactly what S2 creates: content directions / production briefs, not final ideas or publication assets.

## Authority

Base: `main@37292e17cfcbc50588aa248e1b14577637b3f68d`

Frozen dependencies:
- S1 Profile/ProfileVersion authority
- S2 Batch + Editorial Memory + Novelty
- `mk1/arch/EDITORIAL_ENGINE.md`
- `mk1/arch/CONTRACTS.md`
- `mk1/build/WORK_EXECUTION_DIRECTIVE.md`

## Defect

The deterministic candidate source previously used:

`Batch include_topics -> Profile topic_families -> Profile audience -> Profile name`

The last two fallbacks confused audience/identity context with editorial topic authority. An operator reproduced this as an audience sentence rendered as the canonical topic across all four selected directions.

## Corrected authority chain

`Batch include_topics -> accepted Profile topic_families -> no candidate`

Audience text and Profile display names are never promoted to topics.

When no valid topic authority exists, planning remains fail-closed and persists an honest PARTIAL Batch with zero selected items and a remediation message. Novelty/diversity gates are not relaxed.

## Product UX

Create now:
- exposes one compact `Topic for this batch` input in the primary path;
- keeps secondary Goal/Avoid/Format constraints under progressive disclosure;
- calls S2 output `content directions` / `production briefs`;
- labels Topic, Direction and Opening explicitly;
- states that final content is produced in the next stage;
- renames technical metrics to Recent memory / Candidates / Filtered while retaining Planning evidence under disclosure.

## Changed runtime boundaries

- `backend/application/planning/candidates.py`
- `backend/application/planning/service.py`
- `frontend/components/mk1/Mk1BatchCreate.tsx`
- `frontend/components/mk1/mk1-batch-create.module.css`

No ProfileVersion mutation semantics, memory policy, novelty policy, persistence authority, S3 production behavior, approval, scheduling or publishing behavior is changed.

## Tests

Added backend regression coverage proving:
1. raw audience/name cannot become topic;
2. explicit Batch topic is accepted when Profile topic families are empty;
3. missing topic authority yields an honest zero-item PARTIAL Batch.

Updated frontend and browser certification to prove:
- primary topic entry is visible;
- output is described as content directions rather than final content;
- production-brief boundary is explicit;
- existing scroll reachability remains certified.

## Failure / rollback

Rollback is the single S2-Q PR. No persisted schema migration is introduced. Existing historical Batches remain immutable evidence; new planning simply stops creating audience-derived topics.

## Certification gate

Do not mark CLOSED until the exact PR head passes:
- backend-test
- frontend-test
- UI-01-CERT browser
- Docker Compose Local smoke

After merge, rerun the same canonical and Docker gates on the exact merge SHA.
