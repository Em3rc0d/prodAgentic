# MK1-R3 Build Record — Content Quality

Status: CANDIDATE / CERTIFICATION OPEN

Base sealed release: `6b6a73c554eab4926800c5c24df887c70aa678cc`
Candidate branch: `mk1-r3-content-quality`

## Why R3 exists

Manual product testing proved that R2's engine was operational but its provider-free fixture was not a valid proxy for publish-ready editorial quality. Technical QA could pass an artifact whose visible copy still contained demo narration and internal vocabulary. R3 closes that product gap without weakening R2's exact-authority model.

## Implemented deltas

### 1. Profile intelligence without another form

- fallback topic families are derived conservatively from explicit audience text instead of using an entire audience sentence as a topic;
- explicit voice choices feed an allowlisted visual-trait derivation;
- unknown traits remain non-authoritative.

### 2. Generic Creative Brief

Writer and Editor receive a deterministic Profile + Plan brief covering audience, goals, role, voice, channels and a shared publishability bar. No client vertical is encoded in the core.

### 3. Publishability gate

- internal demo/test/workflow/schema leakage is fail-closed;
- prodAgentic control tokens are fail-closed;
- legitimate technical identifiers remain allowed;
- generic hooks, low value density, weak CTA and underused formats produce bounded warnings;
- `APPROVE_TEXT` cannot bypass deterministic blockers.

### 4. Provider-free demo upgraded

The local fixture now creates audience-facing text for text, single-image, carousel and infographic formats. It no longer tells the audience that it is a deterministic R2 demo or asks them to verify persistence.

### 5. Semantic VisualSpec V2 planner behavior

The `VisualSpecV1` contract remains intact while planner behavior is versioned as `mk1-visual-planner-v2`. It adds role-sensitive layouts, semantic visual patterns, bounded icons/dividers and diagrams where the accepted copy structurally supports them. Copy remains referenced from `ContentSpecV1`; the renderer does not invent editorial text.

## Preserved invariants

- immutable ProfileVersion authority;
- exact ContentPlan/Profile digest binding;
- ResearchPack claim boundary;
- typed Writer/Editor contracts;
- bounded editor revision budget;
- immutable ContentRevision lineage;
- VisualSpec copy-reference coverage;
- deterministic renderer boundary;
- QA fail-closed behavior;
- approval freezes exact revision + evidence + asset hashes;
- restart/persistence/manual export requirements from R2.

## Acceptance required before merge

1. R3 regressions pass for multiple Profile/account archetypes.
2. Existing backend/frontend/browser tests remain green.
3. No R2 workflow regression.
4. Demo output contains no R2/test/telemetry copy.
5. Technical-content fixtures can contain legitimate code identifiers without false blocking.
6. Model `APPROVE_TEXT` cannot bypass deterministic publishability blockers.
7. Single image, carousel and infographic VisualSpecs validate and render within geometry limits.
8. Exact candidate head passes CI/workflow matrix.
9. Merge occurs only from that exact accepted head.
10. Exact merged `main` passes post-merge recertification.

## Decision

Not yet certified. This record must remain `CANDIDATE / CERTIFICATION OPEN` until exact-head evidence is green.
