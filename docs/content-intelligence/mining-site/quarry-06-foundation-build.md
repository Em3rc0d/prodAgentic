# Quarry 06 — Foundation Build Evidence

Date: 2026-08-24 / CI observed 2026-08-25 UTC
Branch: `feat/content-intelligence-foundation`
Base: `feat/release-e2e-certification`
Draft PR: #24

## Scope under test

This quarry certifies only:

- `CI-FND-01` — server-resolved workspace scope foundation.
- `CI-MEM-01` — deterministic/versioned canonical content identity.

It does NOT certify semantic memory, embeddings, source grounding, or visual intelligence.

## OBSERVED — implementation

### Workspace foundation

- `ApplicationSettings` now resolves `APP_WORKSPACE_ID` on the server.
- If unset, legacy single-workspace behavior resolves to `legacy-default`.
- Invalid explicit workspace values are rejected.
- `ApplicationContainer` injects the resolved workspace into `PipelineOrchestrator`.
- `GenerationContext` carries `workspace_id`.
- `ContentRun` persists `workspace_id`.
- Legacy ContentRun documents without the field deserialize as `legacy-default`.
- New post projection records also carry the same workspace identity.

### Canonical content identity

`backend/core/content_identity.py` implements canonicalizer `v1`:

1. Require string input.
2. Unicode normalize with NFKC.
3. Case-fold.
4. Collapse/trim whitespace.
5. Preserve punctuation.
6. SHA-256 the canonical UTF-8 text.

The canonicalizer version is stored with the identity so future policy changes do not silently reinterpret historical hashes.

## OBSERVED — first CI run caught a regression

The first CI attempt failed one backend test because `workspace_id` was initially introduced as a required positional field on `GenerationContext`.

Observed result:

- 99 backend tests passed.
- 1 backend test failed.
- Failure was in an existing direct `GenerationContext(...)` construction.
- Frontend was green.

Decision:

Do not modify the existing test to hide the break. Preserve API/model backward compatibility by making `GenerationContext.workspace_id` default to `legacy-default`, while production still injects the server-resolved value explicitly.

This is evidence that the non-regression gate detected a real compatibility issue before the slice progressed.

## OBSERVED — corrected CI run

Head commit under corrected certification:

`e9cbc5095080dadc7f68268cab03df060764180f`

GitHub Actions run:

`32805979051`

Backend job:

- MongoDB 7 service: healthy.
- Python 3.11 setup: success.
- dependency install: success.
- smoke import: success (`Smoke test PASSED`).
- compile check: success.
- pytest: **100 passed, 1 warning in 37.75s**.

The warning is a Starlette/httpx test-client deprecation warning and did not affect correctness.

Frontend job:

- dependency install: success.
- lint: success.
- tests: success.
- production build: success.

## INFERRED

- Adding workspace scope as a backward-compatible server-resolved field does not regress the existing tested generation/review/approval/schedule/publication lifecycle.
- Canonical identity can now serve as a model-independent basis for exact cross-run duplicate memory.

These statements are bounded by the current automated suite; they are not a claim of full multi-tenant SaaS authorization.

## UNKNOWN / NOT YET PROVEN

- Authenticated user-to-workspace ownership mapping.
- Cross-run `content_memory` persistence.
- Exact duplicate lookup against historical published records.
- Semantic similarity.
- Embedding provider/model.
- 1000-workspace performance.

## Verdict

### CI-FND-01

**PASS — FOUNDATION GREEN**

### CI-MEM-01

**PASS — DETERMINISTIC IDENTITY GREEN**

## Next authorized investigation

`CI-MEM-02` — workspace-scoped, idempotent persistence of deterministic memory records.

No embedding/vector implementation is authorized by this quarry.