# PR-CI-FND-01 — Content Intelligence Foundation

Status: IMPLEMENTED / CI GREEN
Branch: `feat/content-intelligence-foundation`
Base: `feat/release-e2e-certification`
Draft PR: #24

## Intent

Introduce the minimum safe foundation required for future cross-run content intelligence without creating a persistent per-user agent or weakening the existing ContentRun lifecycle.

## Implemented behavior

### Server-resolved workspace scope

- Configuration key: `APP_WORKSPACE_ID`.
- Backward-compatible default: `legacy-default` when the key is not configured.
- Explicit blank/invalid values fail settings validation.
- The application container resolves the workspace server-side and passes it into the shared pipeline.
- New ContentRuns persist the resolved `workspace_id`.
- Legacy ContentRuns without the field remain readable as `legacy-default`.
- New post projections persist the same workspace scope.

This is a scope foundation, not a claim that full authenticated multi-tenant ownership is complete.

### Deterministic content identity

Canonicalizer version `v1`:

- NFKC Unicode normalization,
- case-folding,
- whitespace collapse/trim,
- punctuation preserved,
- SHA-256 canonical text identity.

Blank content is rejected and the canonicalizer version is returned with the hash.

## Compatibility correction discovered by CI

The first implementation made `GenerationContext.workspace_id` mandatory and broke an existing direct constructor path.

The suite caught the regression. The field was changed to a backward-compatible `legacy-default` model default while production continues to inject the configured server workspace explicitly.

No existing test was weakened to make the build pass.

## Evidence

Corrected head at certification:

`e9cbc5095080dadc7f68268cab03df060764180f`

GitHub Actions run `32805979051`:

- Backend smoke import: PASS.
- Backend compile: PASS.
- Backend pytest: **100 passed, 1 warning**.
- Frontend lint: PASS.
- Frontend tests: PASS.
- Frontend production build: PASS.

See `docs/content-intelligence/mining-site/quarry-06-foundation-build.md`.

## Non-goals / not implemented

- No `content_memory` collection yet.
- No cross-run duplicate lookup yet.
- No embeddings.
- No vector search.
- No source grounding.
- No visual intent.
- No user Brain or continuous learning.

## Verdict

`CI-FND-01`: PASS.
`CI-MEM-01`: PASS.

Next slice must remain deterministic: `CI-MEM-02` memory persistence.